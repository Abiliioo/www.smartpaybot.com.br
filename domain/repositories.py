# domain/repositories.py
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select, func, and_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Plan, Subscription, User, UserAlertDaily, UserKeyword, ProjectGlobal, ProjectPerUser


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
    category: Optional[str] = None,
    level: Optional[str] = None,
    proposals: Optional[int] = None,
    interested: Optional[int] = None,
    client_rating: Optional[float] = None,
    client_reviews: Optional[int] = None,
) -> tuple[ProjectGlobal, bool, bool]:
    """
    Upsert deduplicando por project_id.
    Retorna (ProjectGlobal, created:bool, updated:bool).
    Campos opcionais só são gravados quando o valor incoming é não-None
    (compatível com registros antigos que têm esses campos como NULL).
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
        # Metadados: só atualiza se o valor chegou (não-None)
        if category is not None and pg.category != category:
            pg.category = category; changed = True
        if level is not None and pg.level != level:
            pg.level = level; changed = True
        if proposals is not None and pg.proposals != proposals:
            pg.proposals = proposals; changed = True
        if interested is not None and pg.interested != interested:
            pg.interested = interested; changed = True
        if client_rating is not None and pg.client_rating != client_rating:
            pg.client_rating = client_rating; changed = True
        if client_reviews is not None and pg.client_reviews != client_reviews:
            pg.client_reviews = client_reviews; changed = True
        if changed:
            db.add(pg)
            db.commit()
        return pg, False, changed  # já existia

    pg = ProjectGlobal(
        project_id=project_id, title=title, link=link,
        published_at=published_at,
        category=category, level=level,
        proposals=proposals, interested=interested,
        client_rating=client_rating, client_reviews=client_reviews,
    )
    db.add(pg)
    try:
        db.commit()
        return pg, True, False  # criado agora
    except IntegrityError:
        db.rollback()
        pg = db.execute(stmt).scalar_one_or_none()
        if pg is None:
            raise
        return pg, False, False


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


# ---------------------------
# Plans
# ---------------------------

def get_plan_by_slug(db: Session, slug: str) -> Optional[Plan]:
    return db.execute(select(Plan).where(Plan.slug == slug)).scalar_one_or_none()


def list_plans(db: Session) -> List[Plan]:
    return list(db.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.id)).scalars())


# ---------------------------
# Subscriptions
# ---------------------------

def get_subscription_by_user(db: Session, user_id: int) -> Optional[Subscription]:
    return db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalar_one_or_none()


def upsert_subscription(db: Session, user_id: int, plan: Plan, status: str = "active") -> Subscription:
    sub = get_subscription_by_user(db, user_id)
    if sub:
        sub.plan_id = plan.id
        sub.status = status
    else:
        sub = Subscription(user_id=user_id, plan_id=plan.id, status=status)
        db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ---------------------------
# Daily alert counter
# ---------------------------

def get_alert_count_today(db: Session, user_id: int) -> int:
    today = date.today()
    row = db.execute(
        select(UserAlertDaily).where(
            UserAlertDaily.user_id == user_id,
            UserAlertDaily.date == today,
        )
    ).scalar_one_or_none()
    return row.alerts_sent if row else 0


def increment_alert_daily(db: Session, user_id: int) -> None:
    today = date.today()
    row = db.execute(
        select(UserAlertDaily).where(
            UserAlertDaily.user_id == user_id,
            UserAlertDaily.date == today,
        )
    ).scalar_one_or_none()
    if row:
        row.alerts_sent += 1
        db.add(row)
    else:
        db.add(UserAlertDaily(user_id=user_id, date=today, alerts_sent=1))
    db.commit()


# ---------------------------
# Admin helpers
# ---------------------------

def list_users_with_plans(db: Session) -> List[Tuple[User, Optional[Plan]]]:
    """
    Retorna (User, Plan|None) para todos os usuários.
    Plan=None significa Free implícito (sem subscription).
    """
    rows = db.execute(
        select(User).order_by(User.id)
    ).scalars().all()

    result: List[Tuple[User, Optional[Plan]]] = []
    for user in rows:
        sub = get_subscription_by_user(db, user.id)
        plan = sub.plan if (sub and sub.status == "active") else None
        result.append((user, plan))
    return result