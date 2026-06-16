# infrastructure/scraping.py
from __future__ import annotations

import asyncio
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from urllib.parse import urljoin

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
# 3) Helpers de parsing
# ============================================================

def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def parse_age_to_minutes(text: str) -> Optional[int]:
    """
    Converte 'Publicado: 31 minutos atrás' / '2 horas' / '3 dias' em minutos.
    """
    t = (text or "").lower()
    m = re.search(r"(?:há\s*)?(\d+)\s*(minuto|minutos|hora|horas|dia|dias)", t)
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


# ============================================================
# 4) Detalhe (best-effort)  — pode falhar sem sessão
# ============================================================

def scrape_99freelas_detail(html: str) -> Dict[str, object]:
    """
    Extrai campos adicionais de uma página de projeto do 99Freelas (detalhe).
    Robusto por regex, mas pode não achar nada se o site entregar HTML “capado”.
    Retorna:
      - category, level
      - age_minutes
      - proposals, interested
      - client_rating, client_reviews
    (nome do cliente propositalmente ignorado)
    """
    soup = BeautifulSoup(html or "", "html.parser")
    flat = _clean_text(soup.get_text(" ", strip=True))

    # Categoria | Nível
    category = None
    level = None
    m_meta = re.search(
        r"([A-Za-zÀ-ÿ0-9,\s&/\-\+]+?)\s*\|\s*(Júnior|Pleno|Intermediário|Sênior|Senior|Iniciante|Especialista|Avançado)",
        flat, re.I
    )
    if m_meta:
        category = _clean_text(m_meta.group(1))
        level = _clean_text(m_meta.group(2).capitalize())

    # Publicado
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

    # Rating / reviews (nome do cliente ignorado)
    client_reviews = None
    m_rev = re.search(r"\((\d+)\s+avalia", flat, re.I)
    if m_rev:
        client_reviews = int(m_rev.group(1))

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
        "client_rating": client_rating,
        "client_reviews": client_reviews,
    }


# ============================================================
# 5) Listagem (confiável, sem sessão)
# ============================================================

def _to_int_or_none(s: str) -> Optional[int]:
    m = re.search(r"(\d+)", s or "")
    return int(m.group(1)) if m else None

def _to_float_or_none(s: str) -> Optional[float]:
    m = re.search(r"(\d+(?:[.,]\d+)?)", s or "")
    return float(m.group(1).replace(",", ".")) if m else None

def scrape_99freelas_list_items(html_text: str) -> List[Dict[str, Any]]:
    """
    Extrai os campos por item de /projects:
      project_id, title, link, category, level, published_ms,
      proposals, interested, client_rating, client_reviews
    (sem nome do cliente).
    """
    from lxml import html as lx
    tree = lx.fromstring(html_text)
    items: List[Dict[str, Any]] = []

    lis = tree.xpath("//ul[contains(@class,'result-list')]/li[contains(@class,'result-item')]")
    for li in lis:
        try:
            pid = (li.get("data-id") or "").strip()
            pid_int = int(pid) if pid.isdigit() else None

            a = li.xpath(".//h1[@class='title']/a | .//h2[@class='title']/a")
            title = (a[0].text or "").strip() if a else ""
            href = a[0].get("href") if a else ""
            link = urljoin("https://www.99freelas.com.br", href) if href else ""

            info_p = li.xpath(".//p[contains(@class,'item-text') and contains(@class,'information')]")
            info_text = " ".join(info_p[0].text_content().split()) if info_p else ""

            # categoria | nível (antes de "Publicado")
            category = level = None
            if "Publicado" in info_text:
                before = info_text.split("Publicado", 1)[0]
                tokens = [t.strip() for t in before.split("|") if t.strip()]
                if tokens:
                    category = tokens[0]
                if len(tokens) >= 2:
                    level = tokens[1]

            # publicado (epoch ms)
            pub_ms = None
            dt_b = li.xpath(".//p[contains(@class,'item-text')][contains(@class,'information')]//b[@class='datetime'][@cp-datetime]")
            if dt_b:
                try:
                    pub_ms = int(dt_b[0].get("cp-datetime"))
                except Exception:
                    pub_ms = None

            # propostas / interessados
            proposals = None
            prop_b = li.xpath("( .//p[contains(@class,'item-text')][contains(@class,'information')]//text()[contains(.,'Propostas')] )[1]/following::b[1]")
            if prop_b:
                proposals = _to_int_or_none(prop_b[0].text_content())
            interested = None
            int_b = li.xpath("( .//p[contains(@class,'item-text')][contains(@class,'information')]//text()[contains(.,'Interessados')] )[1]/following::b[1]")
            if int_b:
                interested = _to_int_or_none(int_b[0].text_content())

            # rating + reviews (sem nome)
            client_rating = None
            star = li.xpath(".//span[contains(@class,'avaliacoes-star')][@data-score]")
            if star:
                client_rating = _to_float_or_none(star[0].get("data-score"))
            client_reviews = None
            rev = li.xpath(".//span[contains(@class,'avaliacoes-text')]")
            if rev:
                txt = " ".join(rev[0].text_content().split()).lower()
                if "sem feedback" in txt:
                    client_reviews = 0
                else:
                    client_reviews = _to_int_or_none(txt)

            items.append({
                "project_id": pid_int,
                "title": title,
                "link": link,
                "category": category,
                "level": level,
                "published_ms": pub_ms,
                "proposals": proposals,
                "interested": interested,
                "client_rating": client_rating,
                "client_reviews": client_reviews,
            })
        except Exception:
            continue

    return items

def enrich_from_list_pages(project_id: int, pages: int = 5, timeout: int = 12) -> Dict[str, Any] | None:
    """
    Busca o item correspondente ao project_id nas primeiras N páginas de /projects
    e retorna o dicionário de campos padronizado (com age_minutes).
    """
    for p in range(1, max(1, pages) + 1):
        url = f"https://www.99freelas.com.br/projects?page={p}"
        try:
            r = requests.get(url, headers=_DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
        except Exception as e:
            logger.info("[scraping] list page %s falhou: %s", p, e)
            continue

        items = scrape_99freelas_list_items(r.text)
        for it in items:
            if it.get("project_id") == project_id:
                # converte published_ms -> age_minutes
                age_minutes = None
                ms = it.get("published_ms")
                if isinstance(ms, int) and ms > 0:
                    try:
                        published_dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
                        age = (datetime.now(tz=timezone.utc) - published_dt).total_seconds() / 60.0
                        age_minutes = max(0, int(age))
                    except Exception:
                        age_minutes = None

                return {
                    "category": it.get("category"),
                    "level": it.get("level"),
                    "age_minutes": age_minutes,
                    "proposals": it.get("proposals"),
                    "interested": it.get("interested"),
                    "client_rating": it.get("client_rating"),
                    "client_reviews": it.get("client_reviews"),
                }
    return None


__all__ = [
    "HttpClient",
    "fetch_html",
    "scrape_99freelas_detail",
    "scrape_99freelas_list_items",
    "enrich_from_list_pages",
    "parse_age_to_minutes",
]
