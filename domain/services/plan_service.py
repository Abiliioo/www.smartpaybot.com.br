# domain/services/plan_service.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..models import Plan, Subscription, User
from ..repositories import (
    get_alert_count_today,
    get_plan_by_slug,
    get_subscription_by_user,
    increment_alert_daily,
    upsert_subscription,
)

FREE_SLUG  = "free"
PRO_SLUG   = "pro"
ADMIN_SLUG = "admin"

# Plano Free de fallback — sem subscription ativa → Free implícito.
_FREE_FALLBACK = Plan(
    id=0,
    slug=FREE_SLUG,
    name="Gratuito",
    max_keywords=3,
    max_alerts_day=10,
    is_active=True,
)

# Plano Admin em memória — is_admin=True → sem nenhum limite.
_ADMIN_PLAN = Plan(
    id=0,
    slug=ADMIN_SLUG,
    name="Admin",
    max_keywords=-1,
    max_alerts_day=-1,
    is_active=True,
)


def get_free_plan(db: Session) -> Plan:
    plan = get_plan_by_slug(db, FREE_SLUG)
    return plan if plan else _FREE_FALLBACK


def get_user_plan(db: Session, user_id: int) -> Plan:
    """
    Retorna o plano ativo do usuário.
    Admin (is_admin=True) → ilimitado, sem verificar subscription.
    Sem assinatura ativa → Free.
    """
    user = db.get(User, user_id)
    if user and user.is_admin:
        return _ADMIN_PLAN
    sub = get_subscription_by_user(db, user_id)
    if sub and sub.status == "active":
        return sub.plan
    return get_free_plan(db)


def is_pro(db: Session, user_id: int) -> bool:
    return get_user_plan(db, user_id).slug == PRO_SLUG


def can_add_keyword(db: Session, user_id: int, current_count: int) -> bool:
    """
    Verifica se o usuário pode adicionar mais keywords.
    current_count = número de keywords que o usuário JÁ tem cadastradas.
    """
    plan = get_user_plan(db, user_id)
    if plan.max_keywords == -1:
        return True
    return current_count < plan.max_keywords


def can_receive_alert_today(db: Session, user_id: int) -> bool:
    plan = get_user_plan(db, user_id)
    if plan.max_alerts_day == -1:
        return True
    today_count = get_alert_count_today(db, user_id)
    return today_count < plan.max_alerts_day


def increment_alert_count(db: Session, user_id: int) -> None:
    """Incrementa o contador diário de alertas do usuário."""
    plan = get_user_plan(db, user_id)
    if plan.max_alerts_day != -1:
        increment_alert_daily(db, user_id)


def set_user_plan(db: Session, user_id: int, plan_slug: str) -> Subscription:
    """
    Atribui um plano ao usuário (cria ou atualiza a subscription).
    Mantém o campo is_subscriber do User em sincronia.
    """
    plan = get_plan_by_slug(db, plan_slug)
    if not plan:
        raise ValueError(f"Plano '{plan_slug}' não encontrado no banco.")

    sub = upsert_subscription(db, user_id=user_id, plan=plan, status="active")

    # Sincroniza flag legada is_subscriber
    user = db.get(User, user_id)
    if user:
        user.is_subscriber = (plan.slug != FREE_SLUG)
        db.add(user)
        db.commit()

    return sub


def get_plan_display(db: Session, user_id: int) -> dict:
    """
    Retorna dados prontos para exibição no template.
    """
    plan = get_user_plan(db, user_id)
    today_alerts = get_alert_count_today(db, user_id)
    return {
        "slug": plan.slug,
        "name": plan.name,
        "max_keywords": plan.max_keywords,
        "max_alerts_day": plan.max_alerts_day,
        "alerts_today": today_alerts,
        "is_pro": plan.slug == PRO_SLUG,
        "is_admin_plan": plan.slug == ADMIN_SLUG,
    }
