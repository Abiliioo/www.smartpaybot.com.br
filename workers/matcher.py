# workers/matcher.py
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from infrastructure.logging import get_logger
from infrastructure.db import SessionLocal
from domain.repositories import (
    get_keywords_by_user,
    iter_new_global_projects_since,
)
from domain.services.projects_service import fanout_project_to_users

logger = get_logger(__name__)

LOOKBACK_MINUTES = int(os.getenv("MATCH_LOOKBACK_MINUTES", "180"))  # 3h padrão

def match_recent_projects() -> int:
    """
    Casa projetos globais recentes com keywords por usuário.
    Usa janela de lookback para simplificar (dedupe no DB garante idempotência).
    Retorna quantas projeções foram criadas.
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    created_total = 0

    with SessionLocal() as db:
        users_keywords: Dict[int, List[str]] = get_keywords_by_user(db)
        if not users_keywords:
            logger.info("[matcher] Nenhum usuário/keyword para casar.")
            return 0

        for gproj in iter_new_global_projects_since(db, since):
            created = fanout_project_to_users(db, global_project=gproj, users_keywords=users_keywords)
            created_total += created

    logger.info("[matcher] lookback=%s min, criados=%s", LOOKBACK_MINUTES, created_total)
    return created_total
