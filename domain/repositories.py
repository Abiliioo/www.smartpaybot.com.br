# domain/repositories.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import ceil
from typing import Any, Collection, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select, func, and_, delete, or_, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Plan, Subscription, User, UserAlertDaily, UserKeyword, ProjectGlobal, ProjectPerUser


ADMIN_USERS_PAGE_SIZE = 20


@dataclass(frozen=True)
class AdminUserListItem:
    user_id: int
    username: str
    email: str
    plan_slug: str
    plan_name: str
    kw_count: int
    alerts_today: int
    total_projects: int
    sub_created_at: Optional[datetime]
    telegram_linked: bool
    monitoring_active: bool
    is_admin: bool


@dataclass(frozen=True)
class AdminUserListPage:
    items: List[AdminUserListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_prev: bool
    has_next: bool


def _escape_like_value(value: str) -> str:
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


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

def count_pending_user_projects(db: Session) -> int:
    stmt = (
        select(func.count())
        .select_from(ProjectPerUser)
        .where(ProjectPerUser.notified_at.is_(None))
    )
    return int(db.execute(stmt).scalar_one() or 0)

def count_eligible_unnotified_user_projects(
    db: Session,
    *,
    max_attempts: int,
    only_user_id: Optional[int] = None,
    only_project_ids: Optional[Collection[int]] = None,
) -> int:
    if only_project_ids is not None and not only_project_ids:
        return 0

    stmt = (
        select(func.count())
        .select_from(ProjectPerUser)
        .join(User, ProjectPerUser.user_id == User.id)
        .where(
            ProjectPerUser.notified_at.is_(None),
            ProjectPerUser.notify_attempts < max_attempts,
            User.bot_active.is_(True),
            User.chat_id.is_not(None),
            func.trim(User.chat_id) != "",
        )
    )
    if only_user_id is not None:
        stmt = stmt.where(ProjectPerUser.user_id == only_user_id)
    if only_project_ids is not None:
        stmt = stmt.where(ProjectPerUser.id.in_(only_project_ids))
    return int(db.execute(stmt).scalar_one() or 0)

def get_eligible_pending_user_ids(
    db: Session,
    *,
    max_attempts: int,
    limit: int = 100,
    only_user_id: Optional[int] = None,
    only_project_ids: Optional[Collection[int]] = None,
) -> List[int]:
    if only_project_ids is not None and not only_project_ids:
        return []

    stmt = (
        select(ProjectPerUser.user_id)
        .join(User, ProjectPerUser.user_id == User.id)
        .where(
            ProjectPerUser.notified_at.is_(None),
            ProjectPerUser.notify_attempts < max_attempts,
            User.bot_active.is_(True),
            User.chat_id.is_not(None),
            func.trim(User.chat_id) != "",
        )
    )
    if only_user_id is not None:
        stmt = stmt.where(ProjectPerUser.user_id == only_user_id)
    if only_project_ids is not None:
        stmt = stmt.where(ProjectPerUser.id.in_(only_project_ids))

    stmt = (
        stmt.group_by(ProjectPerUser.user_id)
        .order_by(func.min(ProjectPerUser.created_at).asc(), ProjectPerUser.user_id.asc())
        .limit(limit)
    )
    return [int(row[0]) for row in db.execute(stmt).all()]

def get_eligible_unnotified_user_projects(
    db: Session,
    *,
    user_id: int,
    max_attempts: int,
    limit: int = 100,
    only_project_ids: Optional[Collection[int]] = None,
) -> List[ProjectPerUser]:
    if only_project_ids is not None and not only_project_ids:
        return []

    stmt = (
        select(ProjectPerUser)
        .join(User, ProjectPerUser.user_id == User.id)
        .where(ProjectPerUser.notified_at.is_(None))
        .where(ProjectPerUser.user_id == user_id)
        .where(ProjectPerUser.notify_attempts < max_attempts)
        .where(User.bot_active.is_(True))
        .where(User.chat_id.is_not(None))
        .where(func.trim(User.chat_id) != "")
    )
    if only_project_ids is not None:
        stmt = stmt.where(ProjectPerUser.id.in_(only_project_ids))

    stmt = stmt.order_by(ProjectPerUser.created_at.asc()).limit(limit)
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

def list_users_with_plans(db: Session) -> List[Tuple[User, Optional[Plan], Optional[Subscription]]]:
    """
    Retorna (User, Plan|None, Subscription|None) para todos os usuários.
    Plan=None significa Free implícito (sem subscription ativa).
    """
    rows = db.execute(
        select(User).order_by(User.id)
    ).scalars().all()

    result: List[Tuple[User, Optional[Plan], Optional[Subscription]]] = []
    for user in rows:
        sub = get_subscription_by_user(db, user.id)
        plan = sub.plan if (sub and sub.status == "active") else None
        result.append((user, plan, sub))
    return result


def list_admin_users_paginated(
    db: Session,
    *,
    q: str = "",
    plan: str = "all",
    monitoring: str = "all",
    telegram: str = "all",
    page: int = 1,
    page_size: int = ADMIN_USERS_PAGE_SIZE,
) -> AdminUserListPage:
    normalized_q = (q or "").strip()[:100]
    plan = plan if plan in {"all", "free", "pro"} else "all"
    monitoring = monitoring if monitoring in {"all", "active", "inactive"} else "all"
    telegram = telegram if telegram in {"all", "linked", "unlinked"} else "all"
    try:
        page = int(page or 1)
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)
    page_size = max(1, int(page_size or ADMIN_USERS_PAGE_SIZE))

    active_subscriptions = (
        select(
            Subscription.user_id.label("user_id"),
            Subscription.created_at.label("sub_created_at"),
            Plan.slug.label("plan_slug"),
            Plan.name.label("plan_name"),
        )
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.status == "active")
        .subquery()
    )
    keyword_counts = (
        select(
            UserKeyword.user_id.label("user_id"),
            func.count(UserKeyword.id).label("kw_count"),
        )
        .group_by(UserKeyword.user_id)
        .subquery()
    )
    project_counts = (
        select(
            ProjectPerUser.user_id.label("user_id"),
            func.count(ProjectPerUser.id).label("total_projects"),
        )
        .group_by(ProjectPerUser.user_id)
        .subquery()
    )
    today_alert_counts = (
        select(
            UserAlertDaily.user_id.label("user_id"),
            func.sum(UserAlertDaily.alerts_sent).label("alerts_today"),
        )
        .where(UserAlertDaily.date == date.today())
        .group_by(UserAlertDaily.user_id)
        .subquery()
    )

    def apply_filters(stmt):
        if normalized_q:
            like_q = f"%{_escape_like_value(normalized_q.lower())}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.username).like(like_q, escape="\\"),
                    func.lower(User.email).like(like_q, escape="\\"),
                )
            )
        if plan == "pro":
            stmt = stmt.where(active_subscriptions.c.plan_slug == "pro")
        elif plan == "free":
            stmt = stmt.where(
                or_(
                    active_subscriptions.c.plan_slug.is_(None),
                    active_subscriptions.c.plan_slug != "pro",
                )
            )
        if monitoring == "active":
            stmt = stmt.where(User.bot_active.is_(True))
        elif monitoring == "inactive":
            stmt = stmt.where(User.bot_active.is_(False))
        if telegram == "linked":
            stmt = stmt.where(User.chat_id.is_not(None), func.trim(User.chat_id) != "")
        elif telegram == "unlinked":
            stmt = stmt.where(or_(User.chat_id.is_(None), func.trim(User.chat_id) == ""))
        return stmt

    base_from = (
        select(User.id)
        .outerjoin(active_subscriptions, active_subscriptions.c.user_id == User.id)
    )
    total_stmt = select(func.count()).select_from(apply_filters(base_from).subquery())
    total = int(db.execute(total_stmt).scalar_one() or 0)
    total_pages = max(1, ceil(total / page_size)) if total else 1
    page = min(page, total_pages)
    offset = (page - 1) * page_size

    rows_stmt = (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            User.email.label("email"),
            User.is_admin.label("is_admin"),
            User.bot_active.label("monitoring_active"),
            case(
                (
                    and_(User.chat_id.is_not(None), func.trim(User.chat_id) != ""),
                    True,
                ),
                else_=False,
            ).label("telegram_linked"),
            active_subscriptions.c.plan_slug,
            active_subscriptions.c.plan_name,
            active_subscriptions.c.sub_created_at,
            func.coalesce(keyword_counts.c.kw_count, 0).label("kw_count"),
            func.coalesce(today_alert_counts.c.alerts_today, 0).label("alerts_today"),
            func.coalesce(project_counts.c.total_projects, 0).label("total_projects"),
        )
        .outerjoin(active_subscriptions, active_subscriptions.c.user_id == User.id)
        .outerjoin(keyword_counts, keyword_counts.c.user_id == User.id)
        .outerjoin(today_alert_counts, today_alert_counts.c.user_id == User.id)
        .outerjoin(project_counts, project_counts.c.user_id == User.id)
    )
    rows_stmt = (
        apply_filters(rows_stmt)
        .order_by(User.id.asc())
        .offset(offset)
        .limit(page_size)
    )

    items: List[AdminUserListItem] = []
    for row in db.execute(rows_stmt).all():
        effective_slug = row.plan_slug or "free"
        effective_name = row.plan_name or "Gratuito"
        items.append(
            AdminUserListItem(
                user_id=int(row.user_id),
                username=row.username,
                email=row.email,
                plan_slug=effective_slug,
                plan_name=effective_name,
                kw_count=int(row.kw_count or 0),
                alerts_today=int(row.alerts_today or 0),
                total_projects=int(row.total_projects or 0),
                sub_created_at=row.sub_created_at,
                telegram_linked=bool(row.telegram_linked),
                monitoring_active=bool(row.monitoring_active),
                is_admin=bool(row.is_admin),
            )
        )

    return AdminUserListPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
    )
