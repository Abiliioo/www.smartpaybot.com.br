# app/routes/admin.py
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.decorators import admin_required
from infrastructure.db import SessionLocal
from infrastructure.logging import get_logger
from domain.repositories import (
    ADMIN_USERS_PAGE_SIZE,
    get_user_by_id,
    list_admin_users_paginated,
    list_plans,
)
from domain.services.plan_service import ADMIN_SLUG, FREE_SLUG, PRO_SLUG, set_user_plan

log = get_logger(__name__)

bp = Blueprint("admin", __name__, url_prefix="/admin")

_PLAN_FILTERS = {"all", FREE_SLUG, PRO_SLUG, ADMIN_SLUG}
_MONITORING_FILTERS = {"all", "active", "inactive"}
_TELEGRAM_FILTERS = {"all", "linked", "unlinked"}


def _parse_page(value: str | None) -> int:
    try:
        return max(1, int(value or 1))
    except (TypeError, ValueError):
        return 1


def _admin_filters_from_args(args) -> dict:
    q = (args.get("q") or "").strip()[:100]
    plan = args.get("plan") or "all"
    monitoring = args.get("monitoring") or "all"
    telegram = args.get("telegram") or "all"
    return {
        "q": q,
        "plan": plan if plan in _PLAN_FILTERS else "all",
        "monitoring": monitoring if monitoring in _MONITORING_FILTERS else "all",
        "telegram": telegram if telegram in _TELEGRAM_FILTERS else "all",
        "page": _parse_page(args.get("page")),
    }


def _admin_filters_from_form(form) -> dict:
    return _admin_filters_from_args(form)


def _redirect_to_admin(filters: dict | None = None):
    filters = filters or {}
    allowed = {
        "q": (filters.get("q") or "").strip()[:100],
        "plan": filters.get("plan") if filters.get("plan") in _PLAN_FILTERS else "all",
        "monitoring": (
            filters.get("monitoring")
            if filters.get("monitoring") in _MONITORING_FILTERS
            else "all"
        ),
        "telegram": (
            filters.get("telegram")
            if filters.get("telegram") in _TELEGRAM_FILTERS
            else "all"
        ),
        "page": _parse_page(filters.get("page")),
    }
    query = {key: value for key, value in allowed.items() if value not in ("", "all", 1)}
    return redirect(url_for("admin.index", **query))


@bp.get("/")
@login_required
@admin_required
def index():
    filters = _admin_filters_from_args(request.args)
    with SessionLocal() as db:
        users_page = list_admin_users_paginated(
            db,
            q=filters["q"],
            plan=filters["plan"],
            monitoring=filters["monitoring"],
            telegram=filters["telegram"],
            page=filters["page"],
            page_size=ADMIN_USERS_PAGE_SIZE,
        )
        plans = list_plans(db)

    return render_template(
        "admin.html",
        rows=users_page.items,
        users_page=users_page,
        page_numbers=list(
            range(
                max(1, users_page.page - 2),
                min(users_page.total_pages, users_page.page + 2) + 1,
            )
        ),
        filters=filters,
        plans=plans,
        free_slug=FREE_SLUG,
        pro_slug=PRO_SLUG,
    )


@bp.post("/users/<int:user_id>/activate-pro")
@login_required
@admin_required
def activate_pro(user_id: int):
    filters = _admin_filters_from_form(request.form)
    try:
        with SessionLocal() as db:
            user = get_user_by_id(db, user_id)
            if not user:
                flash("Usuario nao encontrado.", "danger")
                return _redirect_to_admin(filters)
            username = user.username
            set_user_plan(db, user_id=user_id, plan_slug=PRO_SLUG)
        log.info("[admin] activate_pro: user_id=%s via %s", user_id, request.remote_addr)
        flash(f"Pro ativado para @{username}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        log.exception("[admin] erro ao ativar Pro user_id=%s: %s", user_id, e)
        flash("Erro interno ao ativar Pro.", "danger")
    return _redirect_to_admin(filters)


@bp.post("/users/<int:user_id>/revoke-pro")
@login_required
@admin_required
def revoke_pro(user_id: int):
    filters = _admin_filters_from_form(request.form)
    try:
        with SessionLocal() as db:
            user = get_user_by_id(db, user_id)
            if not user:
                flash("Usuario nao encontrado.", "danger")
                return _redirect_to_admin(filters)
            username = user.username
            set_user_plan(db, user_id=user_id, plan_slug=FREE_SLUG)
        log.info("[admin] revoke_pro: user_id=%s via %s", user_id, request.remote_addr)
        flash(f"Plano de @{username} revertido para Free.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        log.exception("[admin] erro ao revogar Pro user_id=%s: %s", user_id, e)
        flash("Erro interno ao revogar Pro.", "danger")
    return _redirect_to_admin(filters)


@bp.post("/users/<int:user_id>/set-plan")
@login_required
@admin_required
def set_plan(user_id: int):
    filters = _admin_filters_from_form(request.form)
    plan_slug = (request.form.get("plan_slug") or "").strip()
    if plan_slug not in (FREE_SLUG, PRO_SLUG):
        flash("Plano invalido.", "danger")
        return _redirect_to_admin(filters)

    try:
        with SessionLocal() as db:
            set_user_plan(db, user_id=user_id, plan_slug=plan_slug)
        log.info("[admin] user_id=%s plano=%s via %s", user_id, plan_slug, request.remote_addr)
        flash(f"Plano do usuario #{user_id} alterado para {plan_slug.upper()}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        log.exception("[admin] erro ao alterar plano user_id=%s: %s", user_id, e)
        flash("Erro interno ao alterar plano.", "danger")

    return _redirect_to_admin(filters)
