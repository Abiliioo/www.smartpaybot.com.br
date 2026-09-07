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
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import tempfile
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
STATE_SCHEMA_VERSION = 1
STATE_RECENT_IDS_LIMIT = 200
DEFAULT_STATE_PATH = Path("data/collector/collector_state.json")
DEFAULT_FAST_PAGES = 2
DEFAULT_DEEP_PAGES = 10
DEEP_DUE_SECONDS = 540


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
    projects_by_page: list[list[dict]] = field(default_factory=list)


@dataclass
class StateLoadResult:
    status: str
    data: dict = field(default_factory=dict)
    schema_version: int | None = None


@dataclass
class CollectorPlan:
    requested_mode: str
    resolved_mode: str
    pages: int
    fast_pages: int
    deep_pages: int
    deep_due_seconds: int = DEEP_DUE_SECONDS


@dataclass
class ShadowMetrics:
    enabled: bool = True
    state_status: str = "missing"
    previous_recent_ids_count: int = 0
    previous_watermark_published_ms: int | None = None
    hypothetical_stop_page: int | None = None
    pages_saved_hypothetical: int = 0
    missed_new_if_active: int | None = None
    known_projects: int = 0
    unknown_projects: int = 0
    known_ratio: float | None = None
    cycle_usable: bool = False
    reason: str = "not_evaluated"


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
    projects_by_page: list[list[dict]] = []
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
                projects_by_page.append([])
                continue

            if not _has_listing_structure(html_text):
                metrics.parser_failed += 1
                print(f"  Página {page:>2}: parser health falhou")
                projects_by_page.append([])
                continue

            metrics.pages_ok += 1
            metrics.parser_ok += 1
            items = scrape_99freelas_list_items(html_text)
            projects_by_page.append(items)
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

    return CollectResult(
        projects=results,
        metrics=metrics,
        projects_by_page=projects_by_page,
    )


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        normalized = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _load_collector_state(path: Path) -> StateLoadResult:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return StateLoadResult(status="missing")
    except UnicodeDecodeError:
        return StateLoadResult(status="corrupt")
    except OSError:
        return StateLoadResult(status="unreadable")

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return StateLoadResult(status="corrupt")

    if not isinstance(data, dict):
        return StateLoadResult(status="incompatible")

    schema_version = data.get("schema_version")
    if schema_version != STATE_SCHEMA_VERSION:
        return StateLoadResult(
            status="incompatible",
            data=data,
            schema_version=schema_version if isinstance(schema_version, int) else None,
        )

    return StateLoadResult(
        status="loaded",
        data=data,
        schema_version=STATE_SCHEMA_VERSION,
    )


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _recent_project_ids(projects: list[dict]) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for project in projects:
        project_id = project.get("project_id")
        if project_id is None:
            continue
        safe_id = str(project_id)
        if safe_id and safe_id not in seen:
            seen.add(safe_id)
            ids.append(safe_id)
    return ids[-STATE_RECENT_IDS_LIMIT:]


def _watermark_published_ms(projects: list[dict]) -> int | None:
    values = [
        value
        for value in (_safe_int(project.get("published_ms")) for project in projects)
        if value is not None
    ]
    return max(values) if values else None


def _anchors(projects: list[dict]) -> dict[str, str | None]:
    ids = _recent_project_ids(projects)
    return {
        "first_project_id": ids[0] if ids else None,
        "last_project_id": ids[-1] if ids else None,
    }


def _resolve_auto_mode(
    state_load: StateLoadResult,
    started_at: datetime,
) -> str:
    try:
        if state_load.status != "loaded":
            return "deep"

        state = state_load.data
        last_exit_code = _safe_int(state.get("last_exit_code"))
        last_pages_failed = _safe_int(state.get("last_pages_failed"))
        last_parser_failed = _safe_int(state.get("last_parser_failed"))
        last_deep_started_at = _parse_timestamp(state.get("last_deep_started_at"))

        if last_exit_code is None or last_exit_code != EXIT_SUCCESS:
            return "deep"
        if last_pages_failed is None or last_pages_failed > 0:
            return "deep"
        if last_parser_failed is None or last_parser_failed > 0:
            return "deep"
        if last_deep_started_at is None:
            return "deep"

        age_seconds = (started_at - last_deep_started_at).total_seconds()
        if age_seconds < 0 or age_seconds >= DEEP_DUE_SECONDS:
            return "deep"
        return "fast"
    except Exception:
        return "deep"


def _build_collector_plan(
    *,
    requested_mode: str | None,
    pages: int | None,
    fast_pages: int,
    deep_pages: int,
    state_load: StateLoadResult,
    started_at: datetime,
) -> CollectorPlan:
    if requested_mode is None:
        pages_to_collect = pages if pages is not None else settings.SCAN_PAGES
        return CollectorPlan(
            requested_mode="pages",
            resolved_mode="pages",
            pages=pages_to_collect,
            fast_pages=fast_pages,
            deep_pages=deep_pages,
        )

    resolved_mode = (
        _resolve_auto_mode(state_load, started_at)
        if requested_mode == "auto"
        else requested_mode
    )
    return CollectorPlan(
        requested_mode=requested_mode,
        resolved_mode=resolved_mode,
        pages=fast_pages if resolved_mode == "fast" else deep_pages,
        fast_pages=fast_pages,
        deep_pages=deep_pages,
    )


def _is_deep_complete(
    plan: CollectorPlan,
    metrics: CollectorMetrics,
    exit_code: int,
) -> bool:
    return (
        plan.resolved_mode == "deep"
        and metrics.pages_attempted == plan.deep_pages
        and metrics.pages_ok == plan.deep_pages
        and metrics.pages_failed == 0
        and metrics.parser_ok == plan.deep_pages
        and metrics.parser_failed == 0
        and metrics.ingest_received == metrics.projects_unique
        and exit_code == EXIT_SUCCESS
    )


def _arg_present(argv: Sequence[str], name: str) -> bool:
    return any(arg == name or arg.startswith(f"{name}=") for arg in argv)


def _build_next_state(
    previous: dict,
    projects: list[dict],
    metrics: CollectorMetrics,
    exit_code: int,
    started_at: datetime,
    finished_at: datetime,
    plan: CollectorPlan | None = None,
    deep_complete: bool = False,
) -> dict:
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "updated_at": _format_timestamp(finished_at),
        "last_success_at": previous.get("last_success_at"),
        "last_exit_code": exit_code,
        "last_cycle_started_at": _format_timestamp(started_at),
        "last_cycle_finished_at": _format_timestamp(finished_at),
        "watermark_published_ms": previous.get("watermark_published_ms"),
        "recent_project_ids": list(previous.get("recent_project_ids") or [])[
            -STATE_RECENT_IDS_LIMIT:
        ],
        "anchors": previous.get("anchors") if isinstance(previous.get("anchors"), dict) else {},
        "last_pages_attempted": metrics.pages_attempted,
        "last_pages_ok": metrics.pages_ok,
        "last_pages_failed": metrics.pages_failed,
        "last_parser_ok": metrics.parser_ok,
        "last_parser_failed": metrics.parser_failed,
        "last_projects_collected": metrics.projects_collected,
        "last_projects_unique": metrics.projects_unique,
        "last_ingest_received": metrics.ingest_received,
        "last_ingest_inserted": metrics.ingest_inserted,
        "last_ingest_updated": metrics.ingest_updated,
        "last_ingest_skipped": metrics.ingest_skipped,
        "last_deep_started_at": previous.get("last_deep_started_at"),
        "last_collector_mode": plan.resolved_mode if plan else "pages",
    }

    if exit_code == EXIT_SUCCESS:
        state["last_success_at"] = _format_timestamp(finished_at)

    if deep_complete:
        state["last_deep_started_at"] = _format_timestamp(started_at)

    can_refresh_snapshot = plan is None or plan.requested_mode == "pages" or deep_complete
    if exit_code == EXIT_SUCCESS and can_refresh_snapshot:
        recent_ids = _recent_project_ids(projects)
        watermark = _watermark_published_ms(projects)
        if watermark is not None:
            state["watermark_published_ms"] = watermark
        if recent_ids:
            state["recent_project_ids"] = recent_ids
            state["anchors"] = _anchors(projects)

    return state


def _write_collector_state_atomic(path: Path, state: dict) -> str:
    tmp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            json.dump(state, tmp, ensure_ascii=True, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
        return "written"
    except OSError as exc:
        print(f"AVISO: estado local nao gravado ({exc.__class__.__name__})")
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        return "failed"


def _shadow_blocked(
    state_load: StateLoadResult,
    previous_recent_ids_count: int = 0,
    previous_watermark_published_ms: int | None = None,
    reason: str = "not_evaluated",
) -> ShadowMetrics:
    return ShadowMetrics(
        state_status=state_load.status,
        previous_recent_ids_count=previous_recent_ids_count,
        previous_watermark_published_ms=previous_watermark_published_ms,
        missed_new_if_active=None,
        reason=reason,
    )


def _compute_shadow_metrics(
    state_load: StateLoadResult,
    projects_by_page: list[list[dict]],
    metrics: CollectorMetrics,
    collector_mode_resolved: str = "pages",
) -> ShadowMetrics:
    if collector_mode_resolved == "fast":
        previous_recent_ids = []
        previous_watermark = None
        if state_load.status == "loaded":
            previous_recent_ids = state_load.data.get("recent_project_ids") or []
            previous_watermark = _safe_int(state_load.data.get("watermark_published_ms"))
        previous_recent_id_set = {
            str(project_id)
            for project_id in previous_recent_ids
            if project_id is not None
        }
        return _shadow_blocked(
            state_load,
            previous_recent_ids_count=len(previous_recent_id_set),
            previous_watermark_published_ms=previous_watermark,
            reason="fast_cycle_not_full_scan",
        )

    if state_load.status != "loaded":
        return _shadow_blocked(state_load, reason=f"state_{state_load.status}")

    previous_recent_ids = state_load.data.get("recent_project_ids") or []
    previous_recent_id_set = {str(project_id) for project_id in previous_recent_ids if project_id is not None}
    previous_watermark = _safe_int(state_load.data.get("watermark_published_ms"))

    if not previous_recent_id_set:
        return _shadow_blocked(
            state_load,
            previous_recent_ids_count=0,
            previous_watermark_published_ms=previous_watermark,
            reason="state_without_recent_ids",
        )

    if metrics.pages_failed:
        return _shadow_blocked(
            state_load,
            previous_recent_ids_count=len(previous_recent_id_set),
            previous_watermark_published_ms=previous_watermark,
            reason="page_failure",
        )

    if metrics.parser_failed:
        return _shadow_blocked(
            state_load,
            previous_recent_ids_count=len(previous_recent_id_set),
            previous_watermark_published_ms=previous_watermark,
            reason="parser_failure",
        )

    if len(projects_by_page) != metrics.pages_attempted:
        return _shadow_blocked(
            state_load,
            previous_recent_ids_count=len(previous_recent_id_set),
            previous_watermark_published_ms=previous_watermark,
            reason="page_map_unavailable",
        )

    known_projects = 0
    unknown_projects = 0
    stop_page: int | None = None
    stop_index: int | None = None
    project_without_id = False

    for index, page_projects in enumerate(projects_by_page):
        page_known = 0
        page_unknown = 0

        for project in page_projects:
            project_id = project.get("project_id")
            if project_id is None:
                project_without_id = True
                page_unknown += 1
                continue
            if str(project_id) in previous_recent_id_set:
                page_known += 1
            else:
                page_unknown += 1

        known_projects += page_known
        unknown_projects += page_unknown

        if page_projects and page_unknown == 0 and stop_page is None:
            stop_page = index + 1
            stop_index = index

    total_projects = known_projects + unknown_projects
    known_ratio = round(known_projects / total_projects, 4) if total_projects else None

    if project_without_id:
        return ShadowMetrics(
            state_status=state_load.status,
            previous_recent_ids_count=len(previous_recent_id_set),
            previous_watermark_published_ms=previous_watermark,
            known_projects=known_projects,
            unknown_projects=unknown_projects,
            known_ratio=known_ratio,
            missed_new_if_active=None,
            reason="project_without_id",
        )

    if total_projects == 0:
        return ShadowMetrics(
            state_status=state_load.status,
            previous_recent_ids_count=len(previous_recent_id_set),
            previous_watermark_published_ms=previous_watermark,
            known_projects=0,
            unknown_projects=0,
            known_ratio=None,
            missed_new_if_active=None,
            reason="no_projects",
        )

    if stop_page is None or stop_index is None:
        return ShadowMetrics(
            state_status=state_load.status,
            previous_recent_ids_count=len(previous_recent_id_set),
            previous_watermark_published_ms=previous_watermark,
            known_projects=known_projects,
            unknown_projects=unknown_projects,
            known_ratio=known_ratio,
            missed_new_if_active=0,
            reason="boundary_not_found",
        )

    missed_new = 0
    for page_projects in projects_by_page[stop_index + 1 :]:
        for project in page_projects:
            project_id = project.get("project_id")
            if project_id is None or str(project_id) not in previous_recent_id_set:
                missed_new += 1

    return ShadowMetrics(
        state_status=state_load.status,
        previous_recent_ids_count=len(previous_recent_id_set),
        previous_watermark_published_ms=previous_watermark,
        hypothetical_stop_page=stop_page,
        pages_saved_hypothetical=max(metrics.pages_attempted - stop_page, 0),
        missed_new_if_active=missed_new,
        known_projects=known_projects,
        unknown_projects=unknown_projects,
        known_ratio=known_ratio,
        reason="stop_found",
    )


def _finalize_shadow_metrics(
    shadow_metrics: ShadowMetrics | None,
    exit_code: int,
) -> ShadowMetrics:
    if shadow_metrics is None:
        return ShadowMetrics(enabled=False, reason="not_evaluated")

    if exit_code != EXIT_SUCCESS:
        shadow_metrics.cycle_usable = False
        if shadow_metrics.reason in {"stop_found", "boundary_not_found"}:
            shadow_metrics.reason = "real_exit_code_not_success"
        return shadow_metrics

    shadow_metrics.cycle_usable = shadow_metrics.reason in {
        "stop_found",
        "boundary_not_found",
    }
    return shadow_metrics


def _print_telemetry(
    metrics: CollectorMetrics,
    exit_code: int,
    started_at: datetime,
    finished_at: datetime,
    state_load: StateLoadResult,
    state_write_status: str,
    watermark_published_ms: int | None,
    recent_ids_count: int,
    shadow_metrics: ShadowMetrics,
    plan: CollectorPlan | None = None,
    deep_complete: bool = False,
    last_deep_started_at: str | None = None,
) -> None:
    duration_seconds = round((finished_at - started_at).total_seconds(), 3)
    requested_mode = plan.requested_mode if plan else "pages"
    resolved_mode = plan.resolved_mode if plan else "pages"
    fast_pages = plan.fast_pages if plan else DEFAULT_FAST_PAGES
    deep_pages = plan.deep_pages if plan else DEFAULT_DEEP_PAGES
    deep_due_seconds = plan.deep_due_seconds if plan else DEEP_DUE_SECONDS
    payload = {
        "cycle_started_at": _format_timestamp(started_at),
        "cycle_finished_at": _format_timestamp(finished_at),
        "duration_seconds": duration_seconds,
        "exit_code": exit_code,
        "collector_mode_requested": requested_mode,
        "collector_mode_resolved": resolved_mode,
        "collector_fast_pages": fast_pages,
        "collector_deep_pages": deep_pages,
        "collector_deep_due_seconds": deep_due_seconds,
        "collector_deep_complete": deep_complete,
        "collector_last_deep_started_at": last_deep_started_at,
        "pages_attempted": metrics.pages_attempted,
        "pages_ok": metrics.pages_ok,
        "pages_failed": metrics.pages_failed,
        "parser_ok": metrics.parser_ok,
        "parser_failed": metrics.parser_failed,
        "projects_collected": metrics.projects_collected,
        "projects_unique": metrics.projects_unique,
        "ingest_received": metrics.ingest_received,
        "ingest_inserted": metrics.ingest_inserted,
        "ingest_updated": metrics.ingest_updated,
        "ingest_skipped": metrics.ingest_skipped,
        "state_status": state_load.status,
        "state_schema_version": state_load.schema_version,
        "state_write_status": state_write_status,
        "watermark_published_ms": watermark_published_ms,
        "recent_ids_count": recent_ids_count,
        "shadow_enabled": shadow_metrics.enabled,
        "shadow_state_status": shadow_metrics.state_status,
        "shadow_previous_recent_ids_count": shadow_metrics.previous_recent_ids_count,
        "shadow_previous_watermark_published_ms": shadow_metrics.previous_watermark_published_ms,
        "shadow_hypothetical_stop_page": shadow_metrics.hypothetical_stop_page,
        "shadow_pages_saved_hypothetical": shadow_metrics.pages_saved_hypothetical,
        "shadow_missed_new_if_active": shadow_metrics.missed_new_if_active,
        "shadow_known_projects": shadow_metrics.known_projects,
        "shadow_unknown_projects": shadow_metrics.unknown_projects,
        "shadow_known_ratio": shadow_metrics.known_ratio,
        "shadow_cycle_usable": shadow_metrics.cycle_usable,
        "shadow_reason": shadow_metrics.reason,
    }
    print(f"COLLECTOR_TELEMETRY {json.dumps(payload, ensure_ascii=True, sort_keys=True)}")


def _finish_cycle(
    projects: list[dict],
    metrics: CollectorMetrics,
    exit_code: int,
    started_at: datetime,
    state_path: Path,
    state_load: StateLoadResult,
    shadow_metrics: ShadowMetrics | None = None,
    plan: CollectorPlan | None = None,
) -> int:
    finished_at = _utc_now()
    deep_complete = _is_deep_complete(plan, metrics, exit_code) if plan else False
    final_shadow_metrics = _finalize_shadow_metrics(shadow_metrics, exit_code)
    previous_state = state_load.data if state_load.status == "loaded" else {}
    next_state = _build_next_state(
        previous_state,
        projects,
        metrics,
        exit_code,
        started_at,
        finished_at,
        plan,
        deep_complete,
    )
    state_write_status = _write_collector_state_atomic(state_path, next_state)
    _print_summary(metrics, exit_code)
    _print_telemetry(
        metrics,
        exit_code,
        started_at,
        finished_at,
        state_load,
        state_write_status,
        _safe_int(next_state.get("watermark_published_ms")),
        len(next_state.get("recent_project_ids") or []),
        final_shadow_metrics,
        plan,
        deep_complete,
        next_state.get("last_deep_started_at"),
    )
    return exit_code


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
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description="Coleta projetos do 99Freelas e envia para a VPS SmartPayBot."
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help=f"Páginas a raspar (padrão: SCAN_PAGES={settings.SCAN_PAGES})",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "fast", "deep"),
        default=None,
        help="Modo de coleta Fast/Deep. Não combinar com --pages.",
    )
    parser.add_argument(
        "--fast-pages",
        type=int,
        default=DEFAULT_FAST_PAGES,
        help=f"Páginas do modo fast (padrão: {DEFAULT_FAST_PAGES})",
    )
    parser.add_argument(
        "--deep-pages",
        type=int,
        default=DEFAULT_DEEP_PAGES,
        help=f"Páginas do modo deep (padrão: {DEFAULT_DEEP_PAGES})",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Arquivo local descartável de estado do coletor.",
    )
    args = parser.parse_args(raw_args)
    fast_deep_args_present = _arg_present(raw_args, "--fast-pages") or _arg_present(
        raw_args, "--deep-pages"
    )

    if args.pages is not None and args.mode is not None:
        return _config_error("--pages não deve ser combinado com --mode")
    if args.mode is None and fast_deep_args_present:
        return _config_error("--fast-pages/--deep-pages exigem --mode")
    if args.pages is not None and args.pages < 1:
        return _config_error("--pages deve ser maior ou igual a 1")
    if args.fast_pages < 1:
        return _config_error("--fast-pages deve ser maior ou igual a 1")
    if args.deep_pages < 1:
        return _config_error("--deep-pages deve ser maior ou igual a 1")
    if args.fast_pages > args.deep_pages:
        return _config_error("--fast-pages deve ser menor ou igual a --deep-pages")

    started_at = _utc_now()
    state_load = _load_collector_state(args.state_file)
    plan = _build_collector_plan(
        requested_mode=args.mode,
        pages=args.pages,
        fast_pages=args.fast_pages,
        deep_pages=args.deep_pages,
        state_load=state_load,
        started_at=started_at,
    )
    empty_metrics = CollectorMetrics()

    ingest_url = os.getenv("SMARTPAYBOT_INGEST_URL", "").strip()
    token = os.getenv("INTERNAL_INGEST_TOKEN", "").strip()

    if not ingest_url:
        _config_error("SMARTPAYBOT_INGEST_URL não configurado")
        return _finish_cycle([], empty_metrics, EXIT_CONFIG, started_at, args.state_file, state_load, plan=plan)
    if not _valid_ingest_url(ingest_url):
        _config_error("SMARTPAYBOT_INGEST_URL inválida")
        return _finish_cycle([], empty_metrics, EXIT_CONFIG, started_at, args.state_file, state_load, plan=plan)
    if not token:
        _config_error("INTERNAL_INGEST_TOKEN não configurado")
        return _finish_cycle([], empty_metrics, EXIT_CONFIG, started_at, args.state_file, state_load, plan=plan)

    print(
        f"Coletando {plan.pages} página(s) do 99Freelas "
        f"(modo solicitado={plan.requested_mode}, resolvido={plan.resolved_mode})..."
    )
    collect_result = asyncio.run(_collect_pages(plan.pages))
    projects = collect_result.projects
    metrics = collect_result.metrics
    shadow_metrics = _compute_shadow_metrics(
        state_load,
        collect_result.projects_by_page,
        metrics,
        plan.resolved_mode,
    )
    print(f"\nTotal coletado: {len(projects)} projetos únicos")

    if metrics.pages_ok == 0 and metrics.pages_failed > 0:
        exit_code = EXIT_COLLECT_FAILED
        print("ERRO: todas as páginas falharam antes de parser saudável.")
        return _finish_cycle(projects, metrics, exit_code, started_at, args.state_file, state_load, shadow_metrics, plan)

    if metrics.parser_ok == 0 and metrics.parser_failed > 0:
        exit_code = EXIT_PARSER_HEALTH
        print("ERRO: nenhuma página HTTP saudável passou no parser health.")
        return _finish_cycle(projects, metrics, exit_code, started_at, args.state_file, state_load, shadow_metrics, plan)

    if not projects:
        exit_code = EXIT_SUCCESS
        print("Nenhum projeto coletado em página saudável. Nada a enviar.")
        return _finish_cycle(projects, metrics, exit_code, started_at, args.state_file, state_load, shadow_metrics, plan)

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
        return _finish_cycle(projects, metrics, exit_code, started_at, args.state_file, state_load, shadow_metrics, plan)
    except ValueError:
        exit_code = EXIT_INGEST_FAILED
        print(f"ERRO DE INGEST: resposta JSON inválida em {_sanitize_url(ingest_url)}")
        return _finish_cycle(projects, metrics, exit_code, started_at, args.state_file, state_load, shadow_metrics, plan)
    except requests.RequestException as e:
        exit_code = EXIT_INGEST_FAILED
        print(
            "ERRO DE INGEST: "
            f"{e.__class__.__name__} em {_sanitize_url(ingest_url)}"
        )
        return _finish_cycle(projects, metrics, exit_code, started_at, args.state_file, state_load, shadow_metrics, plan)

    exit_code = EXIT_SUCCESS
    return _finish_cycle(projects, metrics, exit_code, started_at, args.state_file, state_load, shadow_metrics, plan)


if __name__ == "__main__":
    raise SystemExit(main())
