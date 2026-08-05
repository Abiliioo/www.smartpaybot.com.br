# domain/services/projects_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..repositories import (
    create_or_get_global_project,
    create_user_project_if_absent,
)
from .keywords_service import clean_keyword, keyword_matches_text
from .plan_service import can_receive_alert_today


@dataclass(frozen=True)
class FanoutProjectResult:
    match_pairs: int = 0
    created: int = 0
    blocked_by_daily_limit: int = 0
    duplicates_or_existing: int = 0


def upsert_global_project(
    db: Session,
    *,
    project_id: int,
    title: str,
    link: str,
    published_at: Optional[datetime] = None,
    category: Optional[str] = None,
    level: Optional[str] = None,
    proposals: Optional[int] = None,
    interested: Optional[int] = None,
    client_rating: Optional[float] = None,
    client_reviews: Optional[int] = None,
):
    """
    Upsert by project_id. Returns (ProjectGlobal, created: bool, updated: bool).
    Optional fields are forwarded to the repository and ignored there when None.
    """
    return create_or_get_global_project(
        db,
        project_id=project_id,
        title=title.strip(),
        link=link.strip(),
        published_at=published_at,
        category=category,
        level=level,
        proposals=proposals,
        interested=interested,
        client_rating=client_rating,
        client_reviews=client_reviews,
    )


def match_users_for_title(
    title: str,
    users_keywords: Dict[int, List[str]],
) -> List[Tuple[int, str]]:
    """
    For a title, return (user_id, matched_keyword) pairs to notify.
    Matching is lexical after normalization/accent removal.
    """
    results: List[Tuple[int, str]] = []

    for user_id, kws in users_keywords.items():
        for kw in kws:
            nkw = clean_keyword(kw)
            if not nkw:
                continue
            if keyword_matches_text(nkw, title):
                results.append((user_id, nkw))
                # Add a break here if the product later wants one keyword per user.
    return results


def fanout_project_to_users(
    db: Session,
    *,
    global_project,
    users_keywords: Dict[int, List[str]],
) -> int:
    """
    Create projects_per_user projections for users whose keywords match.
    Preserves the legacy integer-returning API.
    """
    return fanout_project_to_users_result(
        db,
        global_project=global_project,
        users_keywords=users_keywords,
    ).created


def fanout_project_to_users_result(
    db: Session,
    *,
    global_project,
    users_keywords: Dict[int, List[str]],
) -> FanoutProjectResult:
    """
    Create projections and return aggregate counters for this project's fanout.
    """
    title = global_project.title
    pairs = match_users_for_title(title, users_keywords)

    created = 0
    blocked_by_daily_limit = 0
    duplicates_or_existing = 0
    for user_id, matched_kw in pairs:
        if not can_receive_alert_today(db, user_id):
            blocked_by_daily_limit += 1
            continue
        ppu = create_user_project_if_absent(
            db,
            user_id=user_id,
            global_project=global_project,
            matched_keyword=matched_kw,
        )
        if ppu:
            created += 1
        else:
            duplicates_or_existing += 1
    return FanoutProjectResult(
        match_pairs=len(pairs),
        created=created,
        blocked_by_daily_limit=blocked_by_daily_limit,
        duplicates_or_existing=duplicates_or_existing,
    )
