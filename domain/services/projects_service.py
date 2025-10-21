# domain/services/projects_service.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..repositories import (
    create_or_get_global_project,
    create_user_project_if_absent,
)
from .keywords_service import normalize_text, clean_keyword


def upsert_global_project(
    db: Session,
    *,
    project_id: int,
    title: str,
    link: str,
    published_at: Optional[datetime] = None,
):
    """
    Upsert por project_id. Retorna (ProjectGlobal, created:boolean)
    """
    return create_or_get_global_project(
        db,
        project_id=project_id,
        title=title.strip(),
        link=link.strip(),
        published_at=published_at,
    )


def match_users_for_title(
    title: str,
    users_keywords: Dict[int, List[str]],
) -> List[Tuple[int, str]]:
    """
    Para um título, retorna pares (user_id, matched_keyword) a notificar.
    Matching por substring após normalização/remoção de acentos.
    """
    nt = normalize_text(title)
    results: List[Tuple[int, str]] = []

    for user_id, kws in users_keywords.items():
        for kw in kws:
            nkw = clean_keyword(kw)
            if not nkw:
                continue
            if nkw in nt:
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
        ppu = create_user_project_if_absent(
            db,
            user_id=user_id,
            global_project=global_project,
            matched_keyword=matched_kw,
        )
        if ppu:
            created += 1
    return created
