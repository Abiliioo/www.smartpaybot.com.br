#!/usr/bin/env python3
"""
scripts/migrate_bot_active.py

Migração idempotente: adiciona a coluna `bot_active` à tabela `users`.

Comportamento:
  - Usuários existentes recebem bot_active = 1 (True) por padrão.
  - Pode ser executado mais de uma vez com segurança.

Uso:
    .venv\\Scripts\\python.exe scripts\\migrate_bot_active.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from infrastructure.db import engine

TABLE = "users"


def _existing_columns(conn) -> set[str]:
    result = conn.execute(text(f"PRAGMA table_info({TABLE})"))
    return {row[1] for row in result.fetchall()}


def main() -> None:
    print(f"Migrando tabela '{TABLE}'...")
    with engine.connect() as conn:
        existing = _existing_columns(conn)
        if "bot_active" in existing:
            print("  [ok] 'bot_active' já existe — nada a fazer.")
            return

        conn.execute(text(
            "ALTER TABLE users ADD COLUMN bot_active BOOLEAN NOT NULL DEFAULT 1"
        ))
        conn.commit()
        print("  [+] 'bot_active' BOOLEAN NOT NULL DEFAULT 1 adicionado.")
        print("  [+] Todos os usuários existentes mantêm monitoramento ativo (1).")

    print("\nMigração concluída.")


if __name__ == "__main__":
    main()
