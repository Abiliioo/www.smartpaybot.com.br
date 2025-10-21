# workers/ingestor.py
from __future__ import annotations

import asyncio
import random
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin

from lxml import html

from infrastructure.logging import get_logger
from infrastructure.scraping import HttpClient
from infrastructure.config import get_settings
from infrastructure.db import SessionLocal
from domain.services.projects_service import upsert_global_project

logger = get_logger(__name__)
settings = get_settings()

BASE = "https://www.99freelas.com.br"
LIST_URL = f"{BASE}/projects?page="


def parse_project_id(url: str) -> Optional[int]:
    """
    Extrai o ID numérico do projeto a partir do link completo.
    Exemplos:
      https://www.99freelas.com.br/project/criar-planilha-689946?fs=t
      https://www.99freelas.com.br/project/qualquer-slug-689946
    Retorna None se não encontrar.
    """
    if not url:
        return None
    m = re.search(r"(\d+)(?:\D*$|$)", url)
    try:
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _parse_projects(html_text: str) -> List[Dict[str, object]]:
    """
    Extrai projetos da listagem.
    Estruturas comuns:
      - <h1 class="title"><a href="/project/...">Título</a></h1>
      - <h2 class="title"><a ...>Título</a></h2>
    Retorna: [{"project_id": int, "title": str, "link": str}, ...]
    """
    tree = html.fromstring(html_text)

    # pega anchors de título (variações h1/h2 e eventuais containers)
    anchors = tree.xpath(
        '//h1[contains(@class,"title")]/a | '
        '//h2[contains(@class,"title")]/a | '
        '//*[@class="title"]//a'
    )

    items: List[Dict[str, object]] = []
    for a in anchors:
        try:
            title = (a.text or "").strip()
            href = (a.get("href") or "").strip()
            if not title or not href:
                continue

            # normaliza link absoluto
            link = urljoin(BASE, href)

            # ignora itens que não sejam projetos
            # (ex.: anúncios, filtros, etc.)
            if "/project/" not in link and "/projects/" not in link:
                continue

            pid = parse_project_id(link)
            if pid is None:
                logger.debug("[ingestor] ignorando link sem ID: %s", link)
                continue

            items.append({"project_id": pid, "title": title, "link": link})

        except Exception as e:
            # segue robusto mesmo que um card venha quebrado
            logger.debug("[ingestor] card ignorado por erro: %s", e)
            continue

    return items


async def crawl_once(pages: int | None = None) -> int:
    """
    Varre N páginas e faz upsert em projects_global.
    Deduplicação do ciclo por project_id (evita duplicatas quando o slug/título muda).
    Retorna a contagem de itens únicos vistos nesta rodada (aprox. 'novos no ciclo').
    """
    pages = pages or settings.SCAN_PAGES
    total_seen_raw = 0
    total_seen_unique = 0

    seen_ids: set[int] = set()  # dedupe no ciclo por project_id

    async with HttpClient() as http:
        with SessionLocal() as db:
            for page in range(1, max(1, pages) + 1):
                url = f"{LIST_URL}{page}"
                try:
                    text = await http.get_text(url)
                    items = _parse_projects(text)
                    total_seen_raw += len(items)

                    unique_items: List[Dict[str, object]] = []
                    for it in items:
                        pid = int(it["project_id"])  # garantido pelo parser
                        if pid in seen_ids:
                            continue
                        seen_ids.add(pid)
                        unique_items.append(it)

                    created_count = 0

                    for it in unique_items:
                        _, created = upsert_global_project(
                            db,
                            project_id=int(it["project_id"]),
                            title=str(it["title"]),
                            link=str(it["link"]),
                            published_at=None,  # mantemos aqui; enriquecimento fica para o notifier
                        )
                        if created:
                            created_count += 1

                    total_seen_unique += created_count

                    # backoff curto e aleatório entre páginas (evita agressividade)
                    await asyncio.sleep(0.25 + random.random() * 0.35)

                except Exception as e:
                    logger.error("[ingestor] falha na página %s (%s): %s", page, url, e)

            # commit defensivo (seguro mesmo se upsert já comitar)
            try:
                db.commit()
            except Exception as e:
                logger.exception("[ingestor] commit falhou: %s", e)

    logger.info(
        "[ingestor] páginas=%s, vistos_brutos=%s, vistos_unicos=%s",
        pages, total_seen_raw, total_seen_unique
    )
    return total_seen_unique
