# app/routes/dashboard.py
from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import func, select

from infrastructure.db import SessionLocal
from infrastructure.config import get_settings
from infrastructure.telegram import get_webhook_info, set_webhook, delete_webhook

from domain.models import User, UserKeyword, ProjectPerUser
from domain.services.telegram_link_service import ensure_link_code
from domain.services.keywords_service import parse_keywords_input, clean_keyword
from domain.services.plan_service import can_add_keyword, get_plan_display, get_user_plan
from domain.repositories import (
    list_user_projects, delete_user_keyword,
    list_user_projects_paginated, mark_project_won
)
from infrastructure.timeutils import fmt_br

from app.forms import KeywordsForm

# === Controle do scheduler (ligar/desligar no dashboard) ===
from workers.scheduler import is_running as sched_is_running, start as sched_start, stop as sched_stop

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")
settings = get_settings()

# filtro jinja p/ formatar datetime no fuso BR
def _fmt_br(dt): return fmt_br(dt)

@bp.app_template_filter("fmt_br")
def _register_fmt_br(dt):
    return _fmt_br(dt)


def _default_webhook_url() -> str | None:
    if not settings.PUBLIC_BASE_URL:
        return None
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/webhook/telegram"


# helper: preferir JSON quando X-Requested-With indica fetch/XHR, Accept inclui JSON, ou o corpo é JSON
def _wants_json() -> bool:
    xrw = (request.headers.get("X-Requested-With") or "").lower()
    acc = (request.headers.get("Accept") or "").lower()
    return xrw in ("fetch", "xmlhttprequest") or "application/json" in acc or request.is_json


@bp.get("/")
@login_required
def home():
    with SessionLocal() as db:
        user = db.get(User, int(current_user.id))

        is_linked = bool(user.chat_id)
        # só gera/mostra código se NÃO estiver vinculado
        if is_linked:
            link_code = None
        else:
            link_code = ensure_link_code(db, user, force_new=False)

        keywords = [kw.keyword for kw in user.keywords]
        projects = list_user_projects(db, user_id=user.id, limit=30)

    bot_user = settings.TELEGRAM_BOT_USERNAME or ""
    deep_link = (f"https://t.me/{bot_user}?start={link_code}"
                 if (bot_user and link_code) else None)

    # Webhook info (somente se painel habilitado e usuário admin)
    show_wh = settings.SHOW_WEBHOOK_PANEL and current_user.is_admin
    wh_url = ""
    wh_pending = 0
    wh_last_err = None
    if show_wh:
        wh_info = get_webhook_info() or {}
        wh_url = (wh_info.get("result") or {}).get("url", "")
        wh_pending = (wh_info.get("result") or {}).get("pending_update_count", 0)
        wh_last_err = (wh_info.get("result") or {}).get("last_error_message")

    form = KeywordsForm()
    projects_count = len(projects)
    bot_running = sched_is_running()

    with SessionLocal() as db:
        plan_info = get_plan_display(db, int(current_user.id))

    return render_template(
        "dashboard.html",
        form=form,
        is_linked=is_linked,
        chat_id=user.chat_id,
        link_code=link_code,
        projects_count=projects_count,
        keywords=keywords,
        deep_link=deep_link,
        bot_username=bot_user,
        projects=projects,
        show_webhook_panel=show_wh,
        webhook_url=wh_url,
        webhook_pending=wh_pending,
        webhook_last_error=wh_last_err,
        webhook_default=_default_webhook_url(),
        bot_running=bot_running,
        plan=plan_info,
    )

@bp.get("/projects")
@login_required
def my_projects():
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    page = max(1, page)
    page_size = 20

    with SessionLocal() as db:
        items, total = list_user_projects_paginated(
            db, user_id=int(current_user.id), page=page, page_size=page_size
        )

    pages = max(1, (total + page_size - 1) // page_size)
    has_prev = page > 1
    has_next = page < pages

    # janela de páginas
    window = 2
    start = max(1, page - window)
    end = min(pages, page + window)

    page_numbers = []
    if start > 1:
        page_numbers.append(1)
        if start > 2:
            page_numbers.append(None)
    for p in range(start, end + 1):
        page_numbers.append(p)
    if end < pages:
        if end < pages - 1:
            page_numbers.append(None)
        page_numbers.append(pages)

    return render_template(
        "projects.html",
        items=items,
        page=page,
        pages=pages,
        total=total,
        page_size=page_size,
        has_prev=has_prev,
        has_next=has_next,
        page_numbers=page_numbers,
    )

@bp.post("/projects/mark")
@login_required
def mark_project():
    data = request.get_json(silent=True) or {}
    ppu_id = int(data.get("id") or 0)
    won = bool(data.get("won"))
    raw = str(data.get("value", "") or "").strip()

    # "1.234,56" -> "123456" -> int (centavos)
    norm = raw.replace('.', '').replace(',', '')
    won_cents = int(norm) if norm.isdigit() else 0

    with SessionLocal() as db:
        ok = mark_project_won(
            db, ppu_id=ppu_id, user_id=int(current_user.id),
            won=won, won_cents=won_cents
        )

    return jsonify({"ok": ok}), (200 if ok else 400)




# ---------------------- Webhook (opcional/admin) ----------------------

@bp.post("/webhook/set")
@login_required
def webhook_set():
    if not current_user.is_admin:
        flash("Ação restrita.", "danger")
        return redirect(url_for("dashboard.home"))
    target = (request.form.get("url") or "").strip()
    if not target:
        flash("Informe a URL pública (HTTPS) para o webhook.", "warning")
        return redirect(url_for("dashboard.home"))
    ok = set_webhook(target, drop_pending=True)
    flash("Webhook configurado." if ok else "Falha ao configurar webhook.", "success" if ok else "danger")
    return redirect(url_for("dashboard.home"))


@bp.post("/webhook/delete")
@login_required
def webhook_delete():
    if not current_user.is_admin:
        flash("Ação restrita.", "danger")
        return redirect(url_for("dashboard.home"))
    ok = delete_webhook(drop_pending=True)
    flash("Webhook removido." if ok else "Falha ao remover webhook.", "success" if ok else "danger")
    return redirect(url_for("dashboard.home"))


# ---------------------- Palavras-chave ----------------------

@bp.post("/keywords")
@login_required
def save_keywords():
    form = KeywordsForm()

    # JSON (fetch)
    if _wants_json():
        data = request.get_json(silent=True) or {}
        raw = (data.get("keywords") or "").strip()
        kws = parse_keywords_input(raw)
        if not kws:
            return jsonify({"ok": False, "error": "Nenhuma palavra-chave válida."}), 400

        saved = 0
        with SessionLocal() as db:
            user = db.get(User, int(current_user.id))
            existing = {k.keyword for k in user.keywords}

            plan = get_user_plan(db, user.id)
            max_kw = plan.max_keywords

            # Rejeita se já está no limite
            if max_kw != -1 and len(existing) >= max_kw:
                return jsonify({
                    "ok": False,
                    "error": "limit_reached",
                    "max": max_kw,
                    "plan": plan.slug,
                    "message": (
                        f"Limite de {max_kw} keyword(s) atingido no plano {plan.name}. "
                        "Faça upgrade para o plano Pro."
                    ),
                }), 403

            for kw in kws:
                if kw not in existing:
                    # Para cada nova keyword, verifica se ainda há espaço
                    if max_kw != -1 and (len(existing) + saved) >= max_kw:
                        break
                    db.add(UserKeyword(user_id=user.id, keyword=kw))
                    saved += 1
            db.commit()

            fresh = db.get(User, int(current_user.id))
            new_list = [k.keyword for k in fresh.keywords]

        return jsonify({"ok": True, "saved": saved, "keywords": new_list})

    # fluxo HTML tradicional
    if not form.validate_on_submit():
        flash("Nada para salvar.", "warning")
        return redirect(url_for("dashboard.home"))

    kws = parse_keywords_input(form.keywords.data or "")
    if not kws:
        flash("Nenhuma palavra-chave válida.", "warning")
        return redirect(url_for("dashboard.home"))

    saved = 0
    with SessionLocal() as db:
        user = db.get(User, int(current_user.id))
        existing = {k.keyword for k in user.keywords}

        plan = get_user_plan(db, user.id)
        max_kw = plan.max_keywords

        if max_kw != -1 and len(existing) >= max_kw:
            flash(
                f"Limite de {max_kw} keyword(s) atingido no plano {plan.name}. "
                "Faça upgrade para o plano Pro.",
                "warning",
            )
            return redirect(url_for("dashboard.home"))

        for kw in kws:
            if kw not in existing:
                if max_kw != -1 and (len(existing) + saved) >= max_kw:
                    break
                db.add(UserKeyword(user_id=user.id, keyword=kw))
                saved += 1
        db.commit()

    flash(f"{saved} palavra(s) adicionada(s)." if saved else "Nenhuma nova palavra foi adicionada.", "info")
    return redirect(url_for("dashboard.home"))


@bp.post("/keywords/delete")
@login_required
def delete_keyword():
    # JSON (fetch)
    if _wants_json():
        data = request.get_json(silent=True) or {}
        kw_raw = (data.get("kw") or "").strip()
        if not kw_raw:
            return jsonify({"ok": False, "error": "Keyword inválida."}), 400
        kw = clean_keyword(kw_raw)
        with SessionLocal() as db:
            removed = delete_user_keyword(db, user_id=int(current_user.id), keyword=kw)
            new_list = [k.keyword for k in db.get(User, int(current_user.id)).keywords]
        return jsonify({"ok": True, "removed": bool(removed), "keywords": new_list})

    # fluxo HTML tradicional
    kw_raw = (request.form.get("kw") or "").strip()
    if not kw_raw:
        flash("Keyword inválida.", "warning")
        return redirect(url_for("dashboard.home"))
    kw = clean_keyword(kw_raw)
    with SessionLocal() as db:
        removed = delete_user_keyword(db, user_id=int(current_user.id), keyword=kw)
    flash("Palavra removida." if removed else "Nada foi removido.", "info")
    return redirect(url_for("dashboard.home"))


# ---------------------- Código de vínculo ----------------------

@bp.post("/regen-code")
@login_required
def regen_code():
    with SessionLocal() as db:
        user = db.get(User, int(current_user.id))
        ensure_link_code(db, user, force_new=True)

    flash("Novo código gerado. O anterior foi invalidado.", "info")
    return redirect(url_for("dashboard.home"))


@bp.post("/unlink")
@login_required
def unlink():
    with SessionLocal() as db:
        user = db.get(User, int(current_user.id))
        user.chat_id = None
        db.add(user)
        db.commit()
        ensure_link_code(db, user, force_new=True)
    flash("Telegram desvinculado. Um novo código foi gerado para vincular novamente.", "info")
    return redirect(url_for("dashboard.home"))


# ---------------------- Toggle do Bot (ON/OFF) ----------------------

@bp.post("/bot-toggle")
@login_required
def bot_toggle():
    """
    Alterna o agendador do pipeline.
    Regras:
      - se o usuário não tiver Telegram vinculado, bloqueia (evita ligar sem destino).
    """
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled"))

    # Impede ligar se o usuário não tem chat vinculado
    with SessionLocal() as db:
        user = db.get(User, int(current_user.id))
        if enabled and not user.chat_id:
            return jsonify({
                "ok": False,
                "error": "link_required",
                "running": sched_is_running(),
            }), 400

    try:
        ok = sched_start() if enabled else sched_stop()
    except Exception as e:
        return jsonify({
            "ok": False, "error": "exception", "detail": str(e),
            "running": sched_is_running()
        }), 500


    return jsonify({"ok": bool(ok), "running": sched_is_running()})


# ---------------------- Rotas API ----------------------

@bp.get("/api/summary")
@login_required
def api_summary():
    # usa TZ do app (default São Paulo)
    tzname = getattr(settings, "TZ_NAME", "America/Sao_Paulo")
    tz = ZoneInfo(tzname)

    # limites em horário local
    now_local = datetime.now(tz)
    start_today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_yesterday_local = start_today_local - timedelta(days=1)
    start_week_local = start_today_local - timedelta(days=7)

    # converte limites para UTC (para comparar com created_at do banco)
    start_today_utc = start_today_local.astimezone(ZoneInfo("UTC"))
    start_yesterday_utc = start_yesterday_local.astimezone(ZoneInfo("UTC"))
    start_week_utc = start_week_local.astimezone(ZoneInfo("UTC"))

    with SessionLocal() as db:
        user = db.get(User, int(current_user.id))
        uid = int(user.id)

        def count_between(start=None, end=None) -> int:
            stmt = (
                select(func.count())
                .select_from(ProjectPerUser)
                .where(ProjectPerUser.user_id == uid)
            )
            if start is not None:
                stmt = stmt.where(ProjectPerUser.created_at >= start)
            if end is not None:
                stmt = stmt.where(ProjectPerUser.created_at < end)
            return int(db.execute(stmt).scalar_one() or 0)

        total = count_between()
        today = count_between(start_today_utc)
        yesterday = count_between(start_yesterday_utc, start_today_utc)
        week = count_between(start_week_utc)

        keywords = [k.keyword for k in user.keywords]
        is_linked = bool(user.chat_id)

    return jsonify({
        "ok": True,
        "projects_count": total,
        "counts": {
            "today": today,
            "yesterday": yesterday,
            "week": week,
            "total": total,
        },
        "keywords": keywords,
        "linked": is_linked,
    })




@bp.get("/api/keywords")
@login_required
def api_keywords():
    with SessionLocal() as db:
        user = db.get(User, int(current_user.id))
        keywords = [k.keyword for k in user.keywords]
    return jsonify({"ok": True, "keywords": keywords})


@bp.get("/api/bot")
@login_required
def api_bot():
    """Estado atual do scheduler (para sincronizar o switch/label no front)."""
    return jsonify({"ok": True, "running": sched_is_running()})


@bp.get("/api/kpis")
@login_required
def api_kpis():
    """Indicadores: receita (dia/semana/mês), conversão e ticket médio."""
    # timezone do app (default São Paulo)
    tzname = getattr(settings, "TZ_NAME", "America/Sao_Paulo")
    tz = ZoneInfo(tzname)

    now_local = datetime.now(tz)
    start_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    # semana começando na segunda
    start_week_local = (now_local - timedelta(days=now_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    start_month_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # para comparar com timestamps UTC do banco
    day_utc   = start_day_local.astimezone(ZoneInfo("UTC"))
    week_utc  = start_week_local.astimezone(ZoneInfo("UTC"))
    month_utc = start_month_local.astimezone(ZoneInfo("UTC"))

    with SessionLocal() as db:
        uid = int(current_user.id)

        def sum_won_between(start=None, end=None) -> int:
            stmt = select(func.coalesce(func.sum(ProjectPerUser.won_cents), 0)).where(
                ProjectPerUser.user_id == uid,
                ProjectPerUser.won.is_(True),
            )
            if start is not None:
                stmt = stmt.where(ProjectPerUser.won_at >= start)
            if end is not None:
                stmt = stmt.where(ProjectPerUser.won_at < end)
            return int(db.execute(stmt).scalar_one() or 0)

        def count_won_between(start=None, end=None) -> int:
            stmt = select(func.count()).select_from(ProjectPerUser).where(
                ProjectPerUser.user_id == uid,
                ProjectPerUser.won.is_(True),
            )
            if start is not None:
                stmt = stmt.where(ProjectPerUser.won_at >= start)
            if end is not None:
                stmt = stmt.where(ProjectPerUser.won_at < end)
            return int(db.execute(stmt).scalar_one() or 0)

        total_alerts = int(
            db.execute(
                select(func.count()).select_from(ProjectPerUser).where(ProjectPerUser.user_id == uid)
            ).scalar_one() or 0
        )
        total_won_cnt   = count_won_between()
        total_won_cents = sum_won_between()

        # KPIs
        kpi = {
            "revenue": {
                "day_cents":   sum_won_between(day_utc),
                "week_cents":  sum_won_between(week_utc),
                "month_cents": sum_won_between(month_utc),
                "total_cents": total_won_cents,
            },
            "won": {
                "total": total_won_cnt,
                "today": count_won_between(day_utc),
                "week":  count_won_between(week_utc),
                "month": count_won_between(month_utc),
            },
            "conversion": float(total_won_cnt) / total_alerts if total_alerts else 0.0,
            "ticket_avg_cents": int(total_won_cents / total_won_cnt) if total_won_cnt else 0,
            "alerts_total": total_alerts,
        }

    return jsonify({"ok": True, "kpi": kpi})


@bp.get("/api/kpis/daily")
@login_required
def api_kpis_daily():
    """Soma de receita e quantidade de ganhos por dia (últimos 14 dias)."""
    tzname = getattr(settings, "TZ_NAME", "America/Sao_Paulo")
    tz = ZoneInfo(tzname)
    today_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    days = 14
    start_local = today_local - timedelta(days=days-1)
    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = (today_local + timedelta(days=1)).astimezone(ZoneInfo("UTC"))

    labels = []
    cents = []
    counts = []

    with SessionLocal() as db:
        # pega tudo em uma vez
        stmt = (
            select(ProjectPerUser.won_at, ProjectPerUser.won_cents)
            .where(
                ProjectPerUser.user_id == int(current_user.id),
                ProjectPerUser.won.is_(True),
                ProjectPerUser.won_at >= start_utc,
                ProjectPerUser.won_at < end_utc,
            )
        )
        rows = db.execute(stmt).all()

    # bucket diário (em TZ local)
    buckets_sum = { (start_local + timedelta(days=i)).date(): 0 for i in range(days) }
    buckets_cnt = { (start_local + timedelta(days=i)).date(): 0 for i in range(days) }

    for won_at, value in rows:
        if not won_at:
            continue
        d_local = won_at.astimezone(tz).date()
        if d_local in buckets_sum:
            buckets_sum[d_local] += int(value or 0)
            buckets_cnt[d_local] += 1

    for i in range(days):
        d = (start_local + timedelta(days=i)).date()
        labels.append(d.strftime("%d/%m"))
        cents.append(buckets_sum[d])
        counts.append(buckets_cnt[d])

    return jsonify({"ok": True, "days": days, "labels": labels, "cents": cents, "counts": counts})
