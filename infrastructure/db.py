# infrastructure/db.py
from __future__ import annotations
from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, DeclarativeBase
from sqlalchemy.pool import NullPool
from .config import get_settings

settings = get_settings()

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
