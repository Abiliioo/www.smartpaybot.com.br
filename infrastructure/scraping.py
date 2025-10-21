
# infrastructure/scraping.py
from __future__ import annotations

import asyncio
import re
from typing import Optional, Dict

import aiohttp
import requests
from bs4 import BeautifulSoup

from .config import get_settings
from .logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": settings.USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "close",
}

# ============================================================
# 1) HTTP assíncrono (mantido para quem já usa aiohttp)
# ============================================================

class HttpClient:
    """
    Cliente HTTP assíncrono simples com headers e timeout padronizados.
    Use:  async with HttpClient() as http: html = await http.get_text(url)
    """
    def __init__(self, headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None):
        self.headers = headers or _DEFAULT_HEADERS
        self.timeout = timeout or settings.REQUEST_TIMEOUT
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "HttpClient":
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def get_text(self, url: str) -> str:
        if self._session is None:
            raise RuntimeError("Use 'async with HttpClient()' para criar a sessão.")
        try:
            async with self._session.get(url) as resp:
                text = await resp.text()
                if resp.status != 200:
                    logger.warning("GET %s -> %s: %s", url, resp.status, text[:200])
                return text
        except asyncio.TimeoutError:
            logger.error("Timeout ao acessar %s", url)
            raise
        except aiohttp.ClientError as e:
            logger.error("Erro HTTP ao acessar %s: %s", url, e)
            raise


# ============================================================
# 2) HTTP síncrono (leve) — usado pelo notifier no momento do envio
# ============================================================

def fetch_html(url: str, timeout: Optional[int] = None) -> Optional[str]:
    """
    GET simples com requests, headers padronizados.
    Retorna o HTML (str) ou None em caso de falha.
    """
    t = timeout or settings.REQUEST_TIMEOUT or 12
    try:
        r = requests.get(url, headers=_DEFAULT_HEADERS, timeout=t, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except requests.Timeout:
        logger.error("Timeout ao acessar %s", url)
        return None
    except requests.RequestException as e:
        logger.error("Erro HTTP ao acessar %s: %s", url, e)
        return None


# ============================================================
# 3) Parsing de detalhes do 99Freelas
# ============================================================

def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def parse_age_to_minutes(text: str) -> Optional[int]:
    """
    Converte 'Publicado: 31 minutos atrás' / '2 horas atrás' / '3 dias' em minutos.
    """
    t = (text or "").lower()
    m = re.search(r"(\d+)\s*(minuto|minutos|hora|horas|dia|dias)", t)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if "minuto" in unit:
        return n
    if "hora" in unit:
        return n * 60
    if "dia" in unit:
        return n * 60 * 24
    return None


def scrape_99freelas_detail(html: str) -> Dict[str, object]:
    """
    Extrai campos adicionais de uma página de projeto do 99Freelas.
    Tolerante a mudanças de layout — usa regex sobre o texto geral.
    Campos retornados:
      - category (str)         - level (str)
      - age_minutes (int)      - proposals (int)
      - interested (int)       - client_name (str)
      - client_rating (float)  - client_reviews (int)
    """
    soup = BeautifulSoup(html or "", "html.parser")

    # Texto "achatado" para regex (robus­tez)
    flat = _clean_text(soup.get_text(" ", strip=True))

    # Categoria | Nível (ex.: "Web, Mobile & Software | Intermediário")
    category = None
    level = None
    m_meta = re.search(
        r"([A-Za-zÀ-ÿ0-9,\s&/\-\+]+?)\s*\|\s*(Júnior|Pleno|Intermediário|Sênior|Senior|Avançado)",
        flat, re.I
    )
    if m_meta:
        category = _clean_text(m_meta.group(1))
        level = _clean_text(m_meta.group(2).capitalize())

    # Publicado: ...
    age_minutes = None
    m_pub = re.search(r"(Publicado\s*:\s*[^|•\n\r]+)", flat, re.I)
    if m_pub:
        age_minutes = parse_age_to_minutes(m_pub.group(1))

    # Propostas / Interessados
    def _extract_int(label: str) -> Optional[int]:
        m = re.search(rf"{label}\s*:\s*(\d+)", flat, re.I)
        return int(m.group(1)) if m else None

    proposals = _extract_int("Propostas")
    interested = _extract_int("Interessados")

    # Cliente
    client_name = None
    m_client = re.search(r"Cliente\s*:\s*([A-Za-zÀ-ÿ\.\s]+)", flat, re.I)
    if m_client:
        client_name = _clean_text(m_client.group(1))

    # Avaliações: "(105 avaliações)"
    client_reviews = None
    m_rev = re.search(r"\((\d+)\s+avalia", flat, re.I)
    if m_rev:
        client_reviews = int(m_rev.group(1))

    # Rating aproximado por ícones de estrela (quando houver)
    # Tenta capturar ícones sólidos; se não houver, fica None.
    filled = len(soup.select("i.fas.fa-star, i.fa.fa-star.text-warning, span.fa-star.text-warning"))
    half = len(soup.select("i.fas.fa-star-half, i.fa.fa-star-half"))
    client_rating: Optional[float] = None
    if filled or half:
        client_rating = min(5.0, filled + 0.5 * half)

    return {
        "category": category,
        "level": level,
        "age_minutes": age_minutes,
        "proposals": proposals,
        "interested": interested,
        "client_name": client_name,
        "client_rating": client_rating,
        "client_reviews": client_reviews,
    }


__all__ = [
    "HttpClient",
    "fetch_html",
    "scrape_99freelas_detail",
    "parse_age_to_minutes",
]
