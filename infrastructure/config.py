# infrastructure/config.py
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

def _as_int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default
    
def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")



@dataclass(frozen=True)
class Settings:
    # Ambiente
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = _as_bool(os.getenv("DEBUG"), default=(os.getenv("FLASK_ENV", "development") == "development"))

    # Novo: fuso horário “oficial” do app
    TZ_NAME: str = os.getenv("TZ_NAME", "America/Sao_Paulo")

    # Segurança / sessão
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    CSRF_ENABLED: bool = True

    TELEGRAM_TOKEN: Optional[str] = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_BOT_USERNAME: Optional[str] = os.getenv("TELEGRAM_BOT_USERNAME")
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = os.getenv("TELEGRAM_WEBHOOK_SECRET") or None

    PUBLIC_BASE_URL: Optional[str] = os.getenv("PUBLIC_BASE_URL")
    SHOW_WEBHOOK_PANEL: bool = _env_bool("SHOW_WEBHOOK_PANEL", False)

    # Banco
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///app.db")

    # Redis (opcional)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")

    # Scheduler
    SCHEDULER_ENABLED: bool = _as_bool(os.getenv("SCHEDULER"), default=False)

    # Scan/config do crawler
    SCAN_PAGES: int = _as_int(os.getenv("SCAN_PAGES"), default=10)
    SCAN_MIN_SECONDS: int = _as_int(os.getenv("SCAN_MIN_SECONDS"), default=120)
    SCAN_MAX_SECONDS: int = _as_int(os.getenv("SCAN_MAX_SECONDS"), default=300)

    # HTTP
    REQUEST_TIMEOUT: int = _as_int(os.getenv("REQUEST_TIMEOUT"), default=20)
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    # Log
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
