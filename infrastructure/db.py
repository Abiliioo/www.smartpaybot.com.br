# infrastructure/db.py
from __future__ import annotations
import os
from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, DeclarativeBase
from sqlalchemy.pool import NullPool
from .config import get_settings

settings = get_settings()


def validate_database_url(app_env: str, database_url: str, database_url_was_explicit: bool) -> None:
    """
    Guardrail fail-closed para DATABASE_URL em homologacao. Roda antes de
    create_engine() para nunca abrir conexao com um banco errado.

    Nunca loga/expoe a DATABASE_URL completa (bancos futuros nao-SQLite podem
    carregar credenciais na URL) -- somente esquema/basename quando necessario.
    """
    if app_env != "homologation":
        return

    if not database_url_was_explicit:
        raise RuntimeError(
            "APP_ENV=homologation exige DATABASE_URL configurada explicitamente "
            "no .env; o fallback padrao nunca e aceito em homologacao."
        )

    if not database_url.startswith("sqlite:"):
        scheme = database_url.split(":", 1)[0] if ":" in database_url else "desconhecido"
        raise RuntimeError(
            "APP_ENV=homologation aceita somente DATABASE_URL SQLite nesta fase "
            f"(esquema recebido: {scheme!r})."
        )

    if database_url == "sqlite:///:memory:":
        raise RuntimeError(
            "APP_ENV=homologation exige um banco SQLite persistente; "
            "':memory:' nao e permitido em runtime de homologacao."
        )

    path_part = database_url.split(":///", 1)[-1] if ":///" in database_url else ""
    basename = os.path.basename(path_part)
    if basename != "homolog.db":
        raise RuntimeError(
            "APP_ENV=homologation exige DATABASE_URL SQLite explicita apontando "
            f"para um arquivo 'homolog.db' (nome recebido: {basename!r})."
        )


validate_database_url(settings.APP_ENV, settings.DATABASE_URL, settings.DATABASE_URL_WAS_EXPLICIT)

# SQLite precisa de connect_args para check_same_thread=False quando usado fora de Flask-SQLAlchemy
is_sqlite = settings.DATABASE_URL.startswith("sqlite:")

engine = create_engine(
    settings.DATABASE_URL,
    future=True,
    echo=False,
    poolclass=NullPool if is_sqlite else None,  # simples e robusto por enquanto
    connect_args={"check_same_thread": False} if is_sqlite else {},
    pool_pre_ping=True,
)

class Base(DeclarativeBase):
    pass

# Session por thread (ou greenlet)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
)

def get_db() -> Generator:
    """
    Dependency-style (útil para FastAPI) ou uso direto:
    with SessionLocal() as db: ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db(create_all: bool = False) -> None:
    """
    Inicializa o banco. Em produção, prefira migrações Alembic.
    create_all=True é útil em DEV.
    """
    # Import tardio para registrar modelos
    from domain import models  # noqa: F401
    if create_all:
        Base.metadata.create_all(bind=engine)
