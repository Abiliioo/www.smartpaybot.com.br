# domain/repositories.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select, func, and_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import User, UserKeyword, ProjectGlobal, ProjectPerUser


# ---------------------------
# Users & Keywords
# ---------------------------

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)

def get_user_by_telegram_code(db: Session, code: str) -> Optional[User]:
    if not code:
        return None
    stmt = select(User).where(User.telegram_link_code == code)
    return db.execute(stmt).scalar_one_or_none()

def save_chat_binding(db: Session, user: User, chat_id: str) -> None:
    user.chat_id = str(chat_id)
    user.telegram_link_code = None  # invalida o token após uso
    db.add(user)
    db.commit()

def get_user_keywords(db: Session, user_id: int) -> List[str]:
    stmt = select(UserKeyword.keyword).where(UserKeyword.user_id == user_id)
    return [row[0] for row in db.execute(stmt).all()]

def get_keywords_by_user(db: Session) -> Dict[int, List[str]]:
    """
    Retorna {user_id: [kw1, kw2, ...]} para facilitar o matcher.
    """
    stmt = select(UserKeyword.user_id, UserKeyword.keyword)
    mapping: Dict[int, List[str]] = {}
    for uid, kw in db.execute(stmt).all():
        mapping.setdefault(uid, []).append(kw)
    return mapping


# ---------------------------
# Projects (global)
# ---------------------------

def create_or_get_global_project(
    db: Session,
    *,
    project_id: int,
    title: str,
    link: str,
    published_at: Optional[datetime] = None,
) -> tuple[ProjectGlobal, bool]:
    """
    Upsert deduplicando por project_id.
    Retorna (ProjectGlobal, created:boolean)
    """
    stmt = select(ProjectGlobal).where(ProjectGlobal.project_id == project_id)
    pg = db.execute(stmt).scalar_one_or_none()

    if pg:
        changed = False
        if pg.title != title:
            pg.title = title; changed = True
        if pg.link != link:
            pg.link = link; changed = True
        if published_at and not pg.published_at:
            pg.published_at = published_at; changed = True
        if changed:
            db.add(pg)
            db.commit()
        return pg, False  # <-- já existia

    pg = ProjectGlobal(project_id=project_id, title=title, link=link, published_at=published_at)
    db.add(pg)
    try:
        db.commit()
        return pg, True  # <-- criado agora
    except IntegrityError:
        db.rollback()
        pg = db.execute(stmt).scalar_one_or_none()
        if pg is None:
            raise
        return pg, False


def iter_new_global_projects_since(db: Session, since: datetime) -> Iterable[ProjectGlobal]:
    stmt = (
        select(ProjectGlobal)
        .where(ProjectGlobal.first_seen_at >= since)
        .order_by(ProjectGlobal.first_seen_at.asc())
    )
    for row in db.execute(stmt).scalars():
        yield row


# ---------------------------
# Projects per user (projection)
# ---------------------------

def create_user_project_if_absent(
    db: Session,
    *,
    user_id: int,
    global_project: ProjectGlobal,
    matched_keyword: str,
) -> Optional[ProjectPerUser]:
    """
    Cria projeção para o usuário se ainda não existir (unique por user_id+global_project_id).
    Retorna o objeto criado ou None se já existia.
    """
    # Verifica existência por (user_id, global_project_id)
    stmt = select(ProjectPerUser).where(
        and_(
            ProjectPerUser.user_id == user_id,
            ProjectPerUser.global_project_id == global_project.id,
        )
    )
    exists = db.execute(stmt).scalar_one_or_none()
    if exists:
        return None

    ppu = ProjectPerUser(
        user_id=user_id,
        global_project_id=global_project.id,
        link=global_project.link,      # snapshot do momento do match
        title=global_project.title,    # snapshot do momento do match
        matched_keyword=matched_keyword,
    )
    db.add(ppu)
    try:
        db.commit()
        return ppu
    except IntegrityError:
        db.rollback()
        return None  # outro processo inseriu primeiro

def get_unnotified_user_projects(db: Session, limit: int = 100) -> List[ProjectPerUser]:
    stmt = (
        select(ProjectPerUser)
        .where(ProjectPerUser.notified_at.is_(None))
        .order_by(ProjectPerUser.created_at.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())

def mark_project_notified(db: Session, ppu: ProjectPerUser) -> None:
    ppu.notified_at = func.now()
    db.add(ppu)
    db.commit()

def increment_notify_attempts(db: Session, ppu: ProjectPerUser, *, step: int = 1) -> None:
    ppu.notify_attempts = (ppu.notify_attempts or 0) + step
    db.add(ppu)
    db.commit()


# ---------------------------
# Queries auxiliares
# ---------------------------

def list_user_projects(db: Session, user_id: int, limit: int = 30) -> List[ProjectPerUser]:
    """
    Últimos projetos do usuário (mais recentes primeiro).
    """
    stmt = (
        select(ProjectPerUser)
        .where(ProjectPerUser.user_id == user_id)
        .order_by(ProjectPerUser.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())

def delete_user_keyword(db: Session, user_id: int, keyword: str) -> int:
    """
    Remove exatamente a keyword do usuário (keyword já deve vir normalizada).
    Retorna quantas linhas foram deletadas (0/1).
    """
    stmt = delete(UserKeyword).where(
        and_(UserKeyword.user_id == user_id, UserKeyword.keyword == keyword)
    )
    res = db.execute(stmt)
    db.commit()
    return res.rowcount or 0


def count_user_projects(db, user_id: int) -> int:
    stmt = select(func.count()).select_from(ProjectPerUser).where(ProjectPerUser.user_id == user_id)
    return int(db.execute(stmt).scalar_one() or 0)

def list_user_projects_paginated(db, user_id: int, page: int = 1, page_size: int = 20):
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 20)))
    offset = (page - 1) * page_size
    q = (
        select(ProjectPerUser)
        .where(ProjectPerUser.user_id == user_id)
        .order_by(ProjectPerUser.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(db.scalars(q).all())
    total = count_user_projects(db, user_id)
    return items, total

def mark_project_won(db, ppu_id: int, user_id: int, won: bool, won_cents: int) -> bool:
    ppu = db.get(ProjectPerUser, ppu_id)
    if not ppu or ppu.user_id != user_id:
        return False
    ppu.won = bool(won)
    ppu.won_cents = max(0, int(won_cents or 0))
    ppu.won_at = datetime.now(timezone.utc) if ppu.won else None
    db.add(ppu)
    db.commit()
    return True