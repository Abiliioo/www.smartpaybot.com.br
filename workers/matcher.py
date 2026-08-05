# workers/matcher.py
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Dict, List

from sqlalchemy.orm import Session

from infrastructure.db import SessionLocal
from infrastructure.logging import get_logger
from domain.repositories import (
    get_keywords_by_user,
    iter_new_global_projects_since,
)
from domain.services.projects_service import fanout_project_to_users_result

logger = get_logger(__name__)

LOOKBACK_MINUTES = int(os.getenv("MATCH_LOOKBACK_MINUTES", "180"))  # 3h default
MATCH_RULE = "lexical_boundaries_v1"


def _log_matcher_summary(
    *,
    lookback_min: int,
    users_with_keywords: int,
    keywords_total: int,
    projects_scanned: int,
    projects_with_matches: int,
    match_pairs_total: int,
    projections_created: int,
    blocked_by_daily_limit: int,
    duplicates_or_existing: int,
    started: float,
) -> None:
    duration_ms = max(0, int((perf_counter() - started) * 1000))
    logger.info(
        "[matcher] rule=%s lookback_min=%s users_with_keywords=%s "
        "keywords_total=%s projects_scanned=%s projects_with_matches=%s "
        "match_pairs_total=%s projections_created=%s blocked_by_daily_limit=%s "
        "duplicates_or_existing=%s duration_ms=%s",
        MATCH_RULE,
        lookback_min,
        users_with_keywords,
        keywords_total,
        projects_scanned,
        projects_with_matches,
        match_pairs_total,
        projections_created,
        blocked_by_daily_limit,
        duplicates_or_existing,
        duration_ms,
    )


def match_recent_projects() -> int:
    """
    Match recent global projects against per-user keywords.
    The DB uniqueness constraint keeps the lookback cycle idempotent.
    Returns how many per-user projections were created.
    """
    started = perf_counter()
    since = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    created_total = 0
    projects_scanned = 0
    projects_with_matches = 0
    match_pairs_total = 0
    blocked_by_daily_limit = 0
    duplicates_or_existing = 0

    with SessionLocal() as db:
        users_keywords: Dict[int, List[str]] = get_keywords_by_user(db)
        users_with_keywords = len(users_keywords)
        keywords_total = sum(len(keywords) for keywords in users_keywords.values())
        if not users_keywords:
            logger.info("[matcher] Nenhum usuario/keyword para casar.")
            _log_matcher_summary(
                lookback_min=LOOKBACK_MINUTES,
                users_with_keywords=0,
                keywords_total=0,
                projects_scanned=0,
                projects_with_matches=0,
                match_pairs_total=0,
                projections_created=0,
                blocked_by_daily_limit=0,
                duplicates_or_existing=0,
                started=started,
            )
            return 0

        for gproj in iter_new_global_projects_since(db, since):
            projects_scanned += 1
            result = fanout_project_to_users_result(
                db,
                global_project=gproj,
                users_keywords=users_keywords,
            )
            if result.match_pairs:
                projects_with_matches += 1
            match_pairs_total += result.match_pairs
            created_total += result.created
            blocked_by_daily_limit += result.blocked_by_daily_limit
            duplicates_or_existing += result.duplicates_or_existing

    _log_matcher_summary(
        lookback_min=LOOKBACK_MINUTES,
        users_with_keywords=users_with_keywords,
        keywords_total=keywords_total,
        projects_scanned=projects_scanned,
        projects_with_matches=projects_with_matches,
        match_pairs_total=match_pairs_total,
        projections_created=created_total,
        blocked_by_daily_limit=blocked_by_daily_limit,
        duplicates_or_existing=duplicates_or_existing,
        started=started,
    )
    return created_total
