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



INSECURE_SECRET_KEY_DEFAULT = "dev-secret-key-change-me"

VALID_APP_ENVS = frozenset({"development", "homologation", "production"})


def resolve_app_env(flask_env: str, app_env_raw: Optional[str]) -> str:
    """
    Resolve o valor efetivo de APP_ENV (fail-closed).

    - APP_ENV definido e valido -> usa diretamente.
    - APP_ENV definido e invalido -> RuntimeError.
    - APP_ENV ausente + FLASK_ENV != "production" -> "development".
    - APP_ENV ausente + FLASK_ENV == "production" -> RuntimeError
      (nao ha fallback silencioso para production; precisa ser explicito).
    """
    raw = (app_env_raw or "").strip()
    if raw:
        if raw not in VALID_APP_ENVS:
            raise RuntimeError(
                f"APP_ENV invalido: {raw!r}. Valores permitidos: "
                f"{', '.join(sorted(VALID_APP_ENVS))}."
            )
        return raw
    if flask_env == "production":
        raise RuntimeError(
            "FLASK_ENV=production exige APP_ENV explicito como "
            "'production' ou 'homologation'. Configure APP_ENV no .env."
        )
    return "development"


VALID_TELEGRAM_MODES = frozenset({"disabled", "homologation", "production"})


def resolve_telegram_mode(app_env: str, telegram_mode_raw: Optional[str]) -> str:
    """
    Resolve o valor efetivo de TELEGRAM_MODE (fail-closed).

    - development: ausente -> "disabled"; "disabled"/"homologation" aceitos;
      "production" rejeitado.
    - homologation: exige "homologation" explicito (ausente/disabled/production -> erro).
    - production: exige "production" explicito (ausente/disabled/homologation -> erro).
    - qualquer valor fora de VALID_TELEGRAM_MODES -> erro, independente do ambiente.
    """
    raw = (telegram_mode_raw or "").strip()

    if raw and raw not in VALID_TELEGRAM_MODES:
        raise RuntimeError(
            f"TELEGRAM_MODE invalido: {raw!r}. Valores permitidos: "
            f"{', '.join(sorted(VALID_TELEGRAM_MODES))}."
        )

    if app_env == "development":
        if not raw:
            return "disabled"
        if raw == "production":
            raise RuntimeError(
                "APP_ENV=development nao aceita TELEGRAM_MODE=production."
            )
        return raw

    if app_env == "homologation":
        if raw != "homologation":
            raise RuntimeError(
                "APP_ENV=homologation exige TELEGRAM_MODE=homologation explicito."
            )
        return raw

    if app_env == "production":
        if raw != "production":
            raise RuntimeError(
                "APP_ENV=production exige TELEGRAM_MODE=production explicito."
            )
        return raw

    raise RuntimeError(f"APP_ENV desconhecido ao resolver TELEGRAM_MODE: {app_env!r}.")


def resolve_telegram_expected_bot_id(telegram_mode: str, raw: Optional[str]) -> Optional[int]:
    """
    Resolve TELEGRAM_EXPECTED_BOT_ID (fail-closed). Nao e secret.

    - TELEGRAM_MODE == "disabled": nenhuma identidade e necessaria -> None.
    - TELEGRAM_MODE ativo: obrigatorio, deve ser inteiro positivo.
    """
    if telegram_mode == "disabled":
        return None
    value = (raw or "").strip()
    if not value:
        raise RuntimeError(
            f"TELEGRAM_MODE={telegram_mode} exige TELEGRAM_EXPECTED_BOT_ID configurado."
        )
    try:
        parsed = int(value)
    except ValueError:
        raise RuntimeError(
            f"TELEGRAM_EXPECTED_BOT_ID invalido (nao numerico): {value!r}."
        )
    if parsed <= 0:
        raise RuntimeError(
            f"TELEGRAM_EXPECTED_BOT_ID deve ser um inteiro positivo (recebido: {parsed})."
        )
    return parsed


# Resolvidos uma vez aqui (nao dentro dos defaults do dataclass abaixo) para
# evitar recomputar resolve_app_env/resolve_telegram_mode tres vezes ao
# calcular os campos TELEGRAM_MODE e TELEGRAM_EXPECTED_BOT_ID.
_app_env_for_telegram_defaults = resolve_app_env(os.getenv("FLASK_ENV", "development"), os.getenv("APP_ENV"))
_telegram_mode_for_defaults = resolve_telegram_mode(_app_env_for_telegram_defaults, os.getenv("TELEGRAM_MODE"))


@dataclass(frozen=True)
class Settings:
    # Ambiente
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = _as_bool(os.getenv("DEBUG"), default=(os.getenv("FLASK_ENV", "development") == "development"))
    APP_ENV: str = resolve_app_env(os.getenv("FLASK_ENV", "development"), os.getenv("APP_ENV"))

    # Novo: fuso horário “oficial” do app
    TZ_NAME: str = os.getenv("TZ_NAME", "America/Sao_Paulo")

    # Segurança / sessão
    SECRET_KEY: str = os.getenv("SECRET_KEY", INSECURE_SECRET_KEY_DEFAULT)
    CSRF_ENABLED: bool = True

    TELEGRAM_TOKEN: Optional[str] = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_BOT_USERNAME: Optional[str] = os.getenv("TELEGRAM_BOT_USERNAME")
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = os.getenv("TELEGRAM_WEBHOOK_SECRET") or None
    TELEGRAM_MODE: str = _telegram_mode_for_defaults
    # Nao e secret -- ID numerico do bot, validado via getMe (identity guard).
    TELEGRAM_EXPECTED_BOT_ID: Optional[int] = resolve_telegram_expected_bot_id(
        _telegram_mode_for_defaults, os.getenv("TELEGRAM_EXPECTED_BOT_ID")
    )

    INTERNAL_INGEST_TOKEN: Optional[str] = os.getenv("INTERNAL_INGEST_TOKEN") or None

    PUBLIC_BASE_URL: Optional[str] = os.getenv("PUBLIC_BASE_URL")
    SHOW_WEBHOOK_PANEL: bool = _env_bool("SHOW_WEBHOOK_PANEL", False)

    # Banco
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///app.db")
    # Distingue "DATABASE_URL nao configurada" de "configurada igual ao default",
    # necessario para o guardrail de homologacao em infrastructure/db.py.
    DATABASE_URL_WAS_EXPLICIT: bool = os.getenv("DATABASE_URL") is not None

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


_SESSION_COOKIE_NAMES = {
    "production": "session",
    "homologation": "smartpaybot_homolog_session",
    "development": "session",
}


def session_cookie_name_for_app_env(app_env: str) -> str:
    """
    Deriva deterministicamente o nome do cookie de sessao a partir de
    APP_ENV (SPB-263 B4). Nao e configuravel via variavel de ambiente --
    o operador nao pode configurar homologacao acidentalmente com o
    mesmo nome de cookie de producao. Producao preserva exatamente o
    cookie legado "session" (evita logout global quando o B4 for
    implantado).
    """
    try:
        return _SESSION_COOKIE_NAMES[app_env]
    except KeyError:
        raise RuntimeError(
            f"APP_ENV desconhecido ao resolver SESSION_COOKIE_NAME: {app_env!r}."
        )


_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
