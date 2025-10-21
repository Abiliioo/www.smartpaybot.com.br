# domain/services/telegram_link_service.py
from __future__ import annotations
from typing import Optional
import secrets

from sqlalchemy.orm import Session

from ..models import User

def ensure_link_code(db: Session, user: User, *, force_new: bool = False) -> str:
    """
    Gera (ou retorna) um código único de vínculo Telegram para o usuário.
    Se force_new=True, sempre gera um novo código (inválida o anterior).
    """
    if force_new or not user.telegram_link_code:
        user.telegram_link_code = secrets.token_urlsafe(16)
        db.add(user)
        db.commit()
    return user.telegram_link_code

def invalidate_link_code(db: Session, user: User) -> None:
    """
    Invalida o código atual (após uso).
    """
    user.telegram_link_code = None
    db.add(user)
    db.commit()
