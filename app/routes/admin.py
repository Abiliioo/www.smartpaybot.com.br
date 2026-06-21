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
    get_user_by_id,
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
        for user, plan, sub in users_plans:
            kw_count = len(user.keywords)
            alerts_today = get_alert_count_today(db, user.id)
            total_projects = count_user_projects(db, user.id)
            sub_created_at = (
                sub.created_at.strftime("%d/%m/%Y")
                if sub and sub.created_at else None
            )
            rows.append({
                "user": user,
                "plan": plan,
                "plan_slug": plan.slug if plan else FREE_SLUG,
                "plan_name": plan.name if plan else "Gratuito",
                "kw_count": kw_count,
                "alerts_today": alerts_today,
                "total_projects": total_projects,
                "sub_created_at": sub_created_at,
            })

    return render_template(
        "admin.html",
        rows=rows,
        plans=plans,
        free_slug=FREE_SLUG,
        pro_slug=PRO_SLUG,
    )


@bp.post("/users/<int:user_id>/activate-pro")
@login_required
@admin_required
def activate_pro(user_id: int):
    try:
        with SessionLocal() as db:
            user = get_user_by_id(db, user_id)
            if not user:
                flash("Usuário não encontrado.", "danger")
                return redirect(url_for("admin.index"))
            username = user.username
            set_user_plan(db, user_id=user_id, plan_slug=PRO_SLUG)
        log.info("[admin] activate_pro: user_id=%s (@%s) via %s", user_id, username, request.remote_addr)
        flash(f"✅ Pro ativado para @{username}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        log.exception("[admin] erro ao ativar Pro user_id=%s: %s", user_id, e)
        flash("Erro interno ao ativar Pro.", "danger")
    return redirect(url_for("admin.index"))


@bp.post("/users/<int:user_id>/revoke-pro")
@login_required
@admin_required
def revoke_pro(user_id: int):
    try:
        with SessionLocal() as db:
            user = get_user_by_id(db, user_id)
            if not user:
                flash("Usuário não encontrado.", "danger")
                return redirect(url_for("admin.index"))
            username = user.username
            set_user_plan(db, user_id=user_id, plan_slug=FREE_SLUG)
        log.info("[admin] revoke_pro: user_id=%s (@%s) via %s", user_id, username, request.remote_addr)
        flash(f"Plano de @{username} revertido para Free.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        log.exception("[admin] erro ao revogar Pro user_id=%s: %s", user_id, e)
        flash("Erro interno ao revogar Pro.", "danger")
    return redirect(url_for("admin.index"))


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
        log.info("[admin] user_id=%s → plano=%s (por admin %s)", user_id, plan_slug, getattr(request, "remote_addr", "?"))
        flash(f"Plano do usuário #{user_id} alterado para {plan_slug.upper()}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        log.exception("[admin] erro ao alterar plano user_id=%s: %s", user_id, e)
        flash("Erro interno ao alterar plano.", "danger")

    return redirect(url_for("admin.index"))
