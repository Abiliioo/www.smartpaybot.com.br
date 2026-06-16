# app/__init__.py
from __future__ import annotations

from flask import Flask
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from flask_login import LoginManager, current_user

from infrastructure.config import get_settings
from infrastructure.logging import get_logger

from app.security import AppUser
from infrastructure.db import SessionLocal
from domain.models import User
from datetime import datetime

csrf = CSRFProtect()
login_manager = LoginManager()
log = get_logger(__name__)

def create_app() -> Flask:
    settings = get_settings()
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.utcnow().year}

    # Config essenciais
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["WTF_CSRF_ENABLED"] = settings.CSRF_ENABLED

    # Sessão segura — SECURE só em prod (HTTPS); HTTPONLY e SAMESITE sempre
    app.config["SESSION_COOKIE_SECURE"] = settings.FLASK_ENV == "production"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # CSRF
    csrf.init_app(app)
    app.jinja_env.globals["csrf_token"] = generate_csrf

    # Login
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    app.login_manager = login_manager  # <- ✅ garante atributo no objeto Flask

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return None
        with SessionLocal() as db:
            u = db.get(User, uid)
            return AppUser.from_domain(u) if u else None

    # Expor current_user nos templates
    @app.context_processor
    def inject_current_user():
        return dict(current_user=current_user)

    # Blueprints
    from .routes import register_blueprints
    register_blueprints(app)

    log.info("Flask app criado. ENV=%s DEBUG=%s", settings.FLASK_ENV, settings.DEBUG)
    return app
