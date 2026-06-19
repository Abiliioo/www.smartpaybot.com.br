# app/routes/auth.py
from __future__ import annotations
from infrastructure.logging import get_logger
log = get_logger(__name__)

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.security import AppUser
from app.forms import LoginForm, RegisterForm
from infrastructure.db import SessionLocal
from infrastructure.ratelimit import register_failure, is_limited, reset as rl_reset
from domain.models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

_LOGIN_MAX_ATTEMPTS = 8
_LOGIN_WINDOW = 600  # 10 minutos


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    form = LoginForm()
    return render_template("login.html", form=form)

@bp.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        log.warning("LOGIN validation errors: %s", form.errors)
        flash("Verifique os campos.", "danger")
        return render_template("login.html", form=form)

    username = (form.username.data or "").strip()
    password = form.password.data or ""

    rl_key = f"login:{username.lower()}"
    limited, retry = is_limited(rl_key, max_attempts=_LOGIN_MAX_ATTEMPTS, window_seconds=_LOGIN_WINDOW)
    if limited:
        mins = retry // 60 + 1
        log.warning("LOGIN bloqueado por rate limit: username=%s retry=%ss", username, retry)
        flash(f"Muitas tentativas. Tente novamente em ~{mins} min.", "danger")
        return render_template("login.html", form=form), 429

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            log.info("LOGIN fail: user not found username=%s", username)
            register_failure(rl_key, window_seconds=_LOGIN_WINDOW)
            flash("Usuário ou senha inválidos.", "danger")
            return render_template("login.html", form=form)

        ok = check_password_hash(user.password_hash, password)
        log.info("LOGIN check: username=%s ok=%s", username, ok)
        if not ok:
            register_failure(rl_key, window_seconds=_LOGIN_WINDOW)
            flash("Usuário ou senha inválidos.", "danger")
            return render_template("login.html", form=form)

        rl_reset(rl_key)
        login_user(AppUser.from_domain(user))
        flash("Login efetuado!", "success")
        return redirect(url_for("dashboard.home"))


@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("main.index"))

@bp.get("/register")
def register():
    form = RegisterForm()
    return render_template("register.html", form=form)

@bp.post("/register")
def register_post():
    form = RegisterForm()
    if not form.validate_on_submit():
        log.warning("REGISTER validation errors: %s", form.errors)   # <- LOG
        flash("Verifique os campos.", "danger")
        return render_template("register.html", form=form)

    with SessionLocal() as db:
        exists = db.query(User).filter(
            (User.username == form.username.data.strip()) | (User.email == form.email.data.strip())
        ).first()
        if exists:
            log.info("REGISTER duplicate: username=%s email=%s", form.username.data, form.email.data)  # <- LOG
            flash("Usuário ou email já existem.", "danger")
            return render_template("register.html", form=form)

        u = User(
            username=form.username.data.strip(),
            email=form.email.data.strip(),
            password_hash=generate_password_hash(form.password.data),
            is_admin=False,
            is_subscriber=False,
        )
        db.add(u)
        db.commit()

        log.info("REGISTER ok: user_id=%s username=%s", u.id, u.username)  # <- LOG
        login_user(AppUser.from_domain(u))
        flash("Conta criada!", "success")
        return redirect(url_for("dashboard.home"))
