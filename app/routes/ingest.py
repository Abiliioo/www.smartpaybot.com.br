# app/routes/ingest.py
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, jsonify, request

from app import csrf
from infrastructure.config import get_settings
from infrastructure.logging import get_logger
from infrastructure.db import SessionLocal
from domain.services.projects_service import upsert_global_project

bp = Blueprint("ingest", __name__)
log = get_logger(__name__)

_no_token_warned = False


# ── helpers de coerção segura ──────────────────────────────────────────

def _int_or_none(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _float_or_none(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _str_or_none(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _published_at_from_ms(v) -> Optional[datetime]:
    """Converte epoch em milissegundos para datetime UTC."""
    try:
        ms = int(v)
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


# ── autenticação ──────────────────────────────────────────────────────

def _check_token() -> bool:
    global _no_token_warned
    expected = get_settings().INTERNAL_INGEST_TOKEN
    if expected:
        incoming = request.headers.get("X-Internal-Ingest-Token", "")
        if incoming != expected:
            log.warning("Ingest rejeitado: token inválido ou ausente")
            return False
        return True
    if not _no_token_warned:
        log.warning(
            "INTERNAL_INGEST_TOKEN não configurado — endpoint aceita requisições "
            "sem autenticação. Configure em produção via .env."
        )
        _no_token_warned = True
    return True


# ── pipeline pós-ingest (thread daemon) ─────────────────────────────

def _run_pipeline() -> None:
    try:
        from workers.matcher import match_recent_projects
        from workers.notifier import notify_pending
        match_recent_projects()
        notify_pending()
    except Exception:
        log.exception("[ingest] erro no pipeline pós-ingest")


# ── endpoint ─────────────────────────────────────────────────────────

@bp.post("/ingest/projects")
@csrf.exempt
def ingest_projects():
    if not _check_token():
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True)
    if not data or "projects" not in data:
        return jsonify({"error": 'payload inválido; esperado {"projects": [...]}'}), 400

    projects = data["projects"]
    if not isinstance(projects, list):
        return jsonify({"error": '"projects" deve ser uma lista'}), 400

    received = len(projects)
    inserted = updated = skipped = 0

    with SessionLocal() as db:
        for p in projects:
            # Campos obrigatórios
            try:
                pid = int(p["project_id"])
                title = str(p["title"]).strip()
                link = str(p["link"]).strip()
            except (KeyError, ValueError, TypeError):
                skipped += 1
                continue
            if not pid or not title or not link:
                skipped += 1
                continue

            # Campos opcionais — ignorados silenciosamente se ausentes ou inválidos
            published_at = _published_at_from_ms(p.get("published_ms"))
            category     = _str_or_none(p.get("category"))
            level        = _str_or_none(p.get("level"))
            proposals    = _int_or_none(p.get("proposals"))
            interested   = _int_or_none(p.get("interested"))
            client_rating  = _float_or_none(p.get("client_rating"))
            client_reviews = _int_or_none(p.get("client_reviews"))

            _, created, upd = upsert_global_project(
                db,
                project_id=pid,
                title=title,
                link=link,
                published_at=published_at,
                category=category,
                level=level,
                proposals=proposals,
                interested=interested,
                client_rating=client_rating,
                client_reviews=client_reviews,
            )
            if created:
                inserted += 1
            elif upd:
                updated += 1
            else:
                skipped += 1

    if inserted > 0 or updated > 0:
        t = threading.Thread(target=_run_pipeline, daemon=True)
        t.start()

    log.info(
        "[ingest] recebidos=%s inserted=%s updated=%s skipped=%s",
        received, inserted, updated, skipped,
    )
    return jsonify({
        "received": received,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
    })
