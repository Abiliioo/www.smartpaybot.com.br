#!/usr/bin/env python3
"""
scripts/create_master.py

Cria ou promove um usuário para admin/master no SmartPayBot.
Nenhum dado pessoal é hardcoded — tudo vem de argumentos CLI ou input seguro.

Uso — criar novo usuário admin:
    .venv\\Scripts\\python.exe scripts\\create_master.py --username adm --email adm@exemplo.com

Uso — promover usuário existente a admin:
    .venv\\Scripts\\python.exe scripts\\create_master.py --username joseilton

A senha é solicitada via getpass (nunca aparece na tela nem fica no histórico).
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from infrastructure.db import SessionLocal
from domain.models import User


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria ou promove um usuário para admin/master no SmartPayBot."
    )
    parser.add_argument("--username", required=True, help="Username do usuário")
    parser.add_argument("--email", default=None,
                        help="E-mail (obrigatório ao criar novo usuário; ignorado se o usuário já existir)")
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.username == args.username)
        ).scalar_one_or_none()

        # ── Usuário já existe ──────────────────────────────────────────────
        if user:
            if user.is_admin:
                print(f"Usuário '{args.username}' (id={user.id}) já é admin. Nenhuma alteração.")
            else:
                user.is_admin = True
                user.is_subscriber = True
                db.add(user)
                db.commit()
                print(f"Usuário '{args.username}' (id={user.id}) promovido a admin com sucesso.")
            return

        # ── Criar novo usuário ─────────────────────────────────────────────
        email = (args.email or "").strip()
        if not email:
            email = input("E-mail: ").strip()
        if not email:
            print("ERRO: e-mail é obrigatório para criar um novo usuário.")
            sys.exit(1)

        password = getpass.getpass("Senha: ")
        if not password:
            print("ERRO: a senha não pode ser vazia.")
            sys.exit(1)
        confirm = getpass.getpass("Confirme a senha: ")
        if password != confirm:
            print("ERRO: as senhas não coincidem.")
            sys.exit(1)

        new_user = User(
            username=args.username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=True,
            is_subscriber=True,
        )
        db.add(new_user)
        db.commit()
        print(f"Usuário admin '{args.username}' criado com sucesso (id={new_user.id}).")


if __name__ == "__main__":
    main()
