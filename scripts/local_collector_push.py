#!/usr/bin/env python3
"""
scripts/local_collector_push.py

Executa no ambiente LOCAL (IP residencial) para contornar o bloqueio
do 99Freelas a IPs de datacenter (Cloudflare -> HTTP 403).

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
from dataclasses import dataclass, field
from typing import Sequence
from urllib.parse import urlsplit, urlunsplit

# Garante que o root do projeto está no sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import aiohttp
import requests
from dotenv import load_dotenv
from lxml import html as lx

load_dotenv()

# scraper rico: retorna category, level, published_ms, proposals, interested,
# client_rating, client_reviews além de project_id, title, link
from infrastructure.scraping import HttpClient, scrape_99freelas_list_items
from infrastructure.config import get_settings

settings = get_settings()

BASE_URL = "https://www.99freelas.com.br/projects?page="

EXIT_SUCCESS = 0
EXIT_COLLECT_FAILED = 1
EXIT_CONFIG = 2
EXIT_INGEST_FAILED = 3
EXIT_PARSER_HEALTH = 4

MAX_PAGE_RETRIES = 1
RETRY_BACKOFF_SECONDS = 0.2


@dataclass
class CollectorMetrics:
    pages_attempted: int = 0
    pages_ok: int = 0
    pages_failed: int = 0
    parser_ok: int = 0
    parser_failed: int = 0
    projects_collected: int = 0
    projects_unique: int = 0
    ingest_received: int | None = None
    ingest_inserted: int | None = None
    ingest_updated: int | None = None
    ingest_skipped: int | None = None
    failed_pages: list[int] = field(default_factory=list)


@dataclass
class CollectResult:
    projects: list[dict]
    metrics: CollectorMetrics


def _sanitize_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return "<url-invalida>"


def _valid_ingest_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return parts.scheme in {"http", "https"} and bool(parts.netloc)
    except Exception:
        return False


def _status_from_exception(exc: BaseException) -> int | None:
    status = getattr(exc, "status", None)
    return int(status) if isinstance(status, int) else None


def _is_retryable_collect_error(exc: BaseException) -> bool:
    status = _status_from_exception(exc)
    if status is not None:
        return 500 <= status <= 599
    return isinstance(
        exc,
        (
            asyncio.TimeoutError,
            aiohttp.ClientConnectionError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientOSError,
        ),
    )


def _safe_error_label(exc: BaseException) -> str:
    status = _status_from_exception(exc)
    if status is not None:
        return f"{exc.__class__.__name__}(status={status})"
    return exc.__class__.__name__


def _has_listing_structure(html_text: str) -> bool:
    try:
        tree = lx.fromstring(html_text or "")
    except Exception:
        return False
    result_list = tree.xpath("//ul[contains(@class,'result-list')]")
    result_items = tree.xpath("//li[contains(@class,'result-item')]")
    title_links = tree.xpath(
        "//h1[contains(@class,'title')]/a | "
        "//h2[contains(@class,'title')]/a | "
        "//*[@class='title']//a"
    )
    return bool(result_list or result_items or title_links)


async def _fetch_page_with_retry(http: HttpClient, url: str, page: int) -> str:
    attempts = MAX_PAGE_RETRIES + 1
    safe_url = _sanitize_url(url)
    last_error: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            return await http.get_text(url)
        except Exception as exc:
            last_error = exc
            retryable = _is_retryable_collect_error(exc)
            if retryable and attempt < attempts:
                print(
                    f"  Página {page:>2}: retry {attempt}/{MAX_PAGE_RETRIES} "
                    f"após {_safe_error_label(exc)} em {safe_url}"
                )
                await asyncio.sleep(RETRY_BACKOFF_SECONDS)
                continue
            print(f"  Página {page:>2}: ERRO — {_safe_error_label(exc)} em {safe_url}")
            raise

    raise RuntimeError(f"falha inesperada ao coletar página {page}: {last_error!r}")


async def _collect_pages(pages: int) -> CollectResult:
    seen_ids: set[int] = set()
    results: list[dict] = []
    metrics = CollectorMetrics()

    async with HttpClient() as http:
        for page in range(1, pages + 1):
            metrics.pages_attempted += 1
            url = f"{BASE_URL}{page}"
            try:
                html_text = await _fetch_page_with_retry(http, url, page)
            except Exception:
                metrics.pages_failed += 1
                metrics.failed_pages.append(page)
                continue

            if not _has_listing_structure(html_text):
                metrics.parser_failed += 1
                print(f"  Página {page:>2}: parser health falhou")
                continue

            metrics.pages_ok += 1
            metrics.parser_ok += 1
            items = scrape_99freelas_list_items(html_text)
            metrics.projects_collected += len(items)

            new_on_page = 0
            for item in items:
                pid = item.get("project_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    results.append(item)
                    new_on_page += 1

            metrics.projects_unique = len(results)
            print(
                f"  Página {page:>2}: {len(items)} projetos, {new_on_page} novos "
                f"(total: {len(results)})"
            )
            await asyncio.sleep(0.4)

    return CollectResult(projects=results, metrics=metrics)


def _push(projects: list[dict], url: str, token: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Ingest-Token": token,
    }
    resp = requests.post(url, json={"projects": projects}, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _update_ingest_metrics(metrics: CollectorMetrics, result: dict) -> None:
    def _as_int(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    metrics.ingest_received = _as_int(result.get("received"))
    metrics.ingest_inserted = _as_int(result.get("inserted"))
    metrics.ingest_updated = _as_int(result.get("updated"))
    metrics.ingest_skipped = _as_int(result.get("skipped"))


def _print_summary(metrics: CollectorMetrics, exit_code: int) -> None:
    ingest = "n/a"
    if metrics.ingest_received is not None:
        ingest = (
            f"received={metrics.ingest_received}, "
            f"inserted={metrics.ingest_inserted}, "
            f"updated={metrics.ingest_updated}, "
            f"skipped={metrics.ingest_skipped}"
        )
    print(
        "\nResumo do ciclo: "
        f"pages_attempted={metrics.pages_attempted}, "
        f"pages_ok={metrics.pages_ok}, "
        f"pages_failed={metrics.pages_failed}, "
        f"parser_ok={metrics.parser_ok}, "
        f"parser_failed={metrics.parser_failed}, "
        f"projects_collected={metrics.projects_collected}, "
        f"projects_unique={metrics.projects_unique}, "
        f"ingest={ingest}, "
        f"exit_code={exit_code}"
    )


def _config_error(message: str) -> int:
    print(f"ERRO DE CONFIGURAÇÃO: {message}")
    return EXIT_CONFIG


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Coleta projetos do 99Freelas e envia para a VPS SmartPayBot."
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=settings.SCAN_PAGES,
        help=f"Páginas a raspar (padrão: SCAN_PAGES={settings.SCAN_PAGES})",
    )
    args = parser.parse_args(argv)

    if args.pages < 1:
        return _config_error("--pages deve ser maior ou igual a 1")

    ingest_url = os.getenv("SMARTPAYBOT_INGEST_URL", "").strip()
    token = os.getenv("INTERNAL_INGEST_TOKEN", "").strip()

    if not ingest_url:
        return _config_error("SMARTPAYBOT_INGEST_URL não configurado")
    if not _valid_ingest_url(ingest_url):
        return _config_error("SMARTPAYBOT_INGEST_URL inválida")
    if not token:
        return _config_error("INTERNAL_INGEST_TOKEN não configurado")

    print(f"Coletando {args.pages} página(s) do 99Freelas (scraper rico)...")
    collect_result = asyncio.run(_collect_pages(args.pages))
    projects = collect_result.projects
    metrics = collect_result.metrics
    print(f"\nTotal coletado: {len(projects)} projetos únicos")

    if metrics.pages_ok == 0 and metrics.pages_failed > 0:
        exit_code = EXIT_COLLECT_FAILED
        print("ERRO: todas as páginas falharam antes de parser saudável.")
        _print_summary(metrics, exit_code)
        return exit_code

    if metrics.parser_ok == 0 and metrics.parser_failed > 0:
        exit_code = EXIT_PARSER_HEALTH
        print("ERRO: nenhuma página HTTP saudável passou no parser health.")
        _print_summary(metrics, exit_code)
        return exit_code

    if not projects:
        exit_code = EXIT_SUCCESS
        print("Nenhum projeto coletado em página saudável. Nada a enviar.")
        _print_summary(metrics, exit_code)
        return exit_code

    # Prévia dos campos coletados no primeiro item
    p0 = projects[0]
    campos = [k for k, v in p0.items() if v is not None]
    print(f"Campos disponíveis no 1º item: {campos}")

    print(f"\nEnviando para {_sanitize_url(ingest_url)} ...")
    try:
        result = _push(projects, ingest_url, token)
        _update_ingest_metrics(metrics, result)
        print(
            "\nResultado da VPS: "
            f"received={metrics.ingest_received}, "
            f"inserted={metrics.ingest_inserted}, "
            f"updated={metrics.ingest_updated}, "
            f"skipped={metrics.ingest_skipped}"
        )
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "desconhecido"
        exit_code = EXIT_INGEST_FAILED
        print(f"ERRO DE INGEST: HTTP {status} em {_sanitize_url(ingest_url)}")
        _print_summary(metrics, exit_code)
        return exit_code
    except ValueError:
        exit_code = EXIT_INGEST_FAILED
        print(f"ERRO DE INGEST: resposta JSON inválida em {_sanitize_url(ingest_url)}")
        _print_summary(metrics, exit_code)
        return exit_code
    except requests.RequestException as e:
        exit_code = EXIT_INGEST_FAILED
        print(
            "ERRO DE INGEST: "
            f"{e.__class__.__name__} em {_sanitize_url(ingest_url)}"
        )
        _print_summary(metrics, exit_code)
        return exit_code

    exit_code = EXIT_SUCCESS
    _print_summary(metrics, exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
