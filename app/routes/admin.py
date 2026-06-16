# app/routes/admin.py
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.decorators import admin_required
from infrastructure.db import SessionLocal
from infrastructure.logging import get_logger
from domain.repositories import (
    count_user_projects,
    get_alert_count_today,
    list_plans,
    list_users_with_plans,
)
from domain.services.plan_service import FREE_SLUG, PRO_SLUG, set_user_plan

log = get_logger(__name__)

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@login_required
@admin_required
def index():
    with SessionLocal() as db:
        users_plans = list_users_with_plans(db)
        plans = list_plans(db)

        rows = []
        for user, plan in users_plans:
            kw_count = len(user.keywords)
            alerts_today = get_alert_count_today(db, user.id)
            total_projects = count_user_projects(db, user.id)
            rows.append({
                "user": user,
                "plan": plan,
                "plan_slug": plan.slug if plan else FREE_SLUG,
                "plan_name": plan.name if plan else "Gratuito",
                "kw_count": kw_count,
                "alerts_today": alerts_today,
                "total_projects": total_projects,
            })

    return render_template(
        "admin.html",
        rows=rows,
        plans=plans,
        free_slug=FREE_SLUG,
        pro_slug=PRO_SLUG,
    )


@bp.post("/users/<int:user_id>/set-plan")
@login_required
@admin_required
def set_plan(user_id: int):
    plan_slug = (request.form.get("plan_slug") or "").strip()
    if plan_slug not in (FREE_SLUG, PRO_SLUG):
        flash("Plano inválido.", "danger")
        return redirect(url_for("admin.index"))

    try:
        with SessionLocal() as db:
            sub = set_user_plan(db, user_id=user_id, plan_slug=plan_slug)
        log.info("[admin] user_id=%s → plano=%s (por admin %s)", user_id, plan_slug, getattr(request, 'remote_addr', '?'))
        flash(f"Plano do usuário #{user_id} alterado para {plan_slug.upper()}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        log.exception("[admin] erro ao alterar plano user_id=%s: %s", user_id, e)
        flash("Erro interno ao alterar plano.", "danger")

    return redirect(url_for("admin.index"))
