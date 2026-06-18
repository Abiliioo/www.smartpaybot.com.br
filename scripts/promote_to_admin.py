#!/usr/bin/env python3
"""
scripts/promote_to_admin.py

Promove um usuário existente para admin (is_admin=True).
Idempotente: se já for admin, informa sem falhar.

Uso:
    .venv\\Scripts\\python.exe scripts\\promote_to_admin.py <username>

Exemplos:
    .venv\\Scripts\\python.exe scripts\\promote_to_admin.py joseilton
    .venv\\Scripts\\python.exe scripts\\promote_to_admin.py adm

Códigos de saída:
    0 — sucesso (ou usuário já era admin)
    1 — usuário não encontrado
    2 — uso incorreto (faltou o argumento)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

from infrastructure.db import SessionLocal
from domain.models import User


def promote(username: str) -> int:
    """
    Promove o usuário para admin.
    Retorna código de saída: 0 = ok, 1 = não encontrado.
    """
    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if user is None:
            print(f"ERRO: usuário '{username}' não encontrado no banco.")
            return 1

        if user.is_admin:
            print(
                f"Usuário '{username}' (id={user.id}) já é admin. "
                "Nenhuma alteração necessária."
            )
            return 0

        user.is_admin = True
        user.is_subscriber = True
        db.add(user)
        db.commit()
        print(f"Usuário '{username}' (id={user.id}) promovido a admin com sucesso.")
        return 0


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Uso: python scripts/promote_to_admin.py <username>")
        sys.exit(2)
    sys.exit(promote(sys.argv[1].strip()))


if __name__ == "__main__":
    main()
