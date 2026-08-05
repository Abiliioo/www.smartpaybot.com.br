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
from infrastructure.logging import get_logger

_logger = get_logger(__name__)


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
    Upsert por project_id. Retorna (ProjectGlobal, created:bool, updated:bool).
    Campos opcionais são repassados ao repositório e ignorados se None.
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
    Para um título, retorna pares (user_id, matched_keyword) a notificar.
    Matching lexical apos normalizacao/remocao de acentos.
    """
    results: List[Tuple[int, str]] = []

    for user_id, kws in users_keywords.items():
        for kw in kws:
            nkw = clean_keyword(kw)
            if not nkw:
                continue
            if keyword_matches_text(nkw, title):
                results.append((user_id, nkw))
                # se quiser limitar a uma keyword por user, faça um break aqui
    return results


def fanout_project_to_users(
    db: Session,
    *,
    global_project,
    users_keywords: Dict[int, List[str]],
) -> int:
    """
    Dado um projeto global e o mapa {user_id: [keywords...]},
    cria projeções em projects_per_user para cada user que casar.
    Respeita UNIQUE(user_id, global_project_id).
    Retorna o número de projeções criadas.
    """
    title = global_project.title
    pairs = match_users_for_title(title, users_keywords)

    created = 0
    for user_id, matched_kw in pairs:
        if not can_receive_alert_today(db, user_id):
            _logger.info(
                "[matcher] limite diário atingido para user_id=%s — "
                "projeto global_id=%s não enfileirado.",
                user_id, global_project.project_id,
            )
            continue
        ppu = create_user_project_if_absent(
            db,
            user_id=user_id,
            global_project=global_project,
            matched_keyword=matched_kw,
        )
        if ppu:
            created += 1
    return created


def fanout_project_to_users_result(
    db: Session,
    *,
    global_project,
    users_keywords: Dict[int, List[str]],
) -> FanoutProjectResult:
    """
    Cria projecoes e retorna contadores agregados do fanout do projeto.
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
