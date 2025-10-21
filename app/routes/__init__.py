# app/routes/__init__.py
from __future__ import annotations
from flask import Blueprint, Flask, render_template

from .webhook_telegram import bp as webhook_bp
from .auth import bp as auth_bp
from .dashboard import bp as dashboard_bp

bp_main = Blueprint("main", __name__)

@bp_main.get("/")
def index():
    return render_template("index.html")

@bp_main.get("/healthz")
def healthz():
    return {"status": "ok"}

def register_blueprints(app: Flask) -> None:
    app.register_blueprint(bp_main)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(webhook_bp, url_prefix="/webhook")
