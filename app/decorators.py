# app/decorators.py
from __future__ import annotations

from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user

from infrastructure.db import SessionLocal
from domain.services.plan_service import get_user_plan, PRO_SLUG


def admin_required(f):
    """Restringe a rota a usuários com is_admin=True."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def plan_required(min_slug: str = PRO_SLUG):
    """
    Restringe a rota a usuários no plano mínimo indicado.
    Uso: @plan_required("pro")

    Se o usuário não tiver o plano exigido, redireciona para o dashboard
    com flash informativo (não expõe a existência de um plano de upgrade).
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))

            with SessionLocal() as db:
                plan = get_user_plan(db, int(current_user.id))

            # Hierarquia simples: free < pro
            _order = {"free": 0, "pro": 1}
            user_level = _order.get(plan.slug, 0)
            required_level = _order.get(min_slug, 1)

            if user_level < required_level:
                flash(
                    f"Este recurso é exclusivo do plano Pro. "
                    f"Seu plano atual é {plan.name}.",
                    "warning",
                )
                return redirect(url_for("dashboard.home"))

            return f(*args, **kwargs)
        return wrapper
    return decorator
