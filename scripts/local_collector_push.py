#!/usr/bin/env python3
"""
scripts/local_collector_push.py

Executa no ambiente LOCAL (IP residencial) para contornar o bloqueio
do 99Freelas a IPs de datacenter (Cloudflare → HTTP 403).

Raspa N páginas de /projects usando o scraper rico (categoria, nível,
propostas, avaliação, etc.), deduplica por project_id e envia o lote
via POST para o endpoint protegido na VPS.

Uso:
    .venv\\Scripts\\python.exe scripts\\local_collector_push.py [--pages N]

Variáveis exigidas no .env local:
    SMARTPAYBOT_INGEST_URL=https://smartpaybot.com.br/internal/ingest/projects
    INTERNAL_INGEST_TOKEN=<mesmo token configurado no .env da VPS>
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Garante que o root do projeto está no sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import requests
from dotenv import load_dotenv

load_dotenv()

# scraper rico: retorna category, level, published_ms, proposals, interested,
# client_rating, client_reviews além de project_id, title, link
from infrastructure.scraping import HttpClient, scrape_99freelas_list_items
from infrastructure.config import get_settings

settings = get_settings()

BASE_URL = "https://www.99freelas.com.br/projects?page="


async def _collect_pages(pages: int) -> list[dict]:
    seen_ids: set[int] = set()
    results: list[dict] = []

    async with HttpClient() as http:
        for page in range(1, pages + 1):
            url = f"{BASE_URL}{page}"
            try:
                html_text = await http.get_text(url)
                items = scrape_99freelas_list_items(html_text)
                new_on_page = 0
                for item in items:
                    pid = item.get("project_id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        results.append(item)
                        new_on_page += 1
                print(f"  Página {page:>2}: {len(items)} projetos, {new_on_page} novos "
                      f"(total: {len(results)})")
                await asyncio.sleep(0.4)
            except Exception as e:
                print(f"  Página {page:>2}: ERRO — {e}")

    return results


def _push(projects: list[dict], url: str, token: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Ingest-Token": token,
    }
    resp = requests.post(url, json={"projects": projects}, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coleta projetos do 99Freelas e envia para a VPS SmartPayBot."
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=settings.SCAN_PAGES,
        help=f"Páginas a raspar (padrão: SCAN_PAGES={settings.SCAN_PAGES})",
    )
    args = parser.parse_args()

    ingest_url = os.getenv("SMARTPAYBOT_INGEST_URL", "").strip()
    token      = os.getenv("INTERNAL_INGEST_TOKEN", "").strip()

    if not ingest_url:
        print("ERRO: SMARTPAYBOT_INGEST_URL não configurado no .env")
        sys.exit(1)
    if not token:
        print("AVISO: INTERNAL_INGEST_TOKEN não configurado — requisição sem autenticação.")

    print(f"Coletando {args.pages} página(s) do 99Freelas (scraper rico)...")
    projects = asyncio.run(_collect_pages(args.pages))
    print(f"\nTotal coletado: {len(projects)} projetos únicos")

    if not projects:
        print("Nenhum projeto coletado. Nada a enviar.")
        sys.exit(0)

    # Prévia dos campos coletados no primeiro item
    if projects:
        p0 = projects[0]
        campos = [k for k, v in p0.items() if v is not None]
        print(f"Campos disponíveis no 1º item: {campos}")

    print(f"\nEnviando para {ingest_url} ...")
    try:
        result = _push(projects, ingest_url, token)
        print(f"\nResultado da VPS: {result}")
    except requests.HTTPError as e:
        print(f"ERRO HTTP {e.response.status_code}: {e.response.text}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"ERRO de conexão: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
