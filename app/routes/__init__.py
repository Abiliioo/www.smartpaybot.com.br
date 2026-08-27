# app/routes/__init__.py
from __future__ import annotations
from flask import Blueprint, Flask, current_app, render_template
from flask_login import current_user

from app.frontend_manifest import (
    ViteManifestError,
    default_manifest_path,
    load_vite_assets,
)
from .webhook_telegram import bp as webhook_bp
from .auth import bp as auth_bp
from .dashboard import bp as dashboard_bp
from .admin import bp as admin_bp
from .ingest import bp as ingest_bp

bp_main = Blueprint("main", __name__)


def _vite_manifest_path():
    manifest_path = current_app.config.get("VITE_MANIFEST_PATH")
    if manifest_path:
        return manifest_path
    return default_manifest_path(current_app.static_folder)


@bp_main.get("/")
def index():
    if current_app.config.get("REACT_LANDING_ENABLED"):
        try:
            assets = load_vite_assets(_vite_manifest_path())
        except ViteManifestError:
            return render_template("index.html")

        return render_template(
            "react_shell.html",
            js_file=assets.js_file,
            css_files=assets.css_files,
            page_mode="landing",
            title="SmartPayBot",
            robots="index, follow",
        )
    return render_template("index.html")


@bp_main.get("/pro")
def pro():
    is_subscriber = False
    is_admin_user = False
    if current_user.is_authenticated:
        is_admin_user = bool(current_user.is_admin)
        if not is_admin_user:
            from infrastructure.db import SessionLocal
            from domain.services.plan_service import is_pro as _is_pro
            with SessionLocal() as db:
                is_subscriber = _is_pro(db, int(current_user.id))
    return render_template("pro.html", is_subscriber=is_subscriber, is_admin_user=is_admin_user)


@bp_main.get("/ui-preview")
def ui_preview():
    try:
        assets = load_vite_assets(_vite_manifest_path())
    except ViteManifestError:
        return (
            "React build nao encontrado. Rode `npm.cmd run build` em `frontend`.",
            503,
        )

    return render_template(
        "react_shell.html",
        js_file=assets.js_file,
        css_files=assets.css_files,
        page_mode="preview",
        title="SmartPayBot UI Preview",
        robots="noindex, nofollow",
    )


@bp_main.get("/healthz")
def healthz():
    return {"status": "ok"}


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(bp_main)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(webhook_bp, url_prefix="/webhook")
    app.register_blueprint(admin_bp)
    app.register_blueprint(ingest_bp, url_prefix="/internal")
