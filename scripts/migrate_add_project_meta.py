#!/usr/bin/env python3
"""
scripts/migrate_add_project_meta.py

Migração idempotente: adiciona colunas de metadados ricos à tabela
projects_global (category, level, proposals, interested, client_rating,
client_reviews).

Pode ser executado mais de uma vez com segurança — colunas já existentes
são ignoradas silenciosamente.

Uso:
    .venv\\Scripts\\python.exe scripts\\migrate_add_project_meta.py
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

# (nome_da_coluna, tipo_SQLite)
COLUMNS = [
    ("category",       "TEXT"),
    ("level",          "TEXT"),
    ("proposals",      "INTEGER"),
    ("interested",     "INTEGER"),
    ("client_rating",  "REAL"),
    ("client_reviews", "INTEGER"),
]

TABLE = "projects_global"


def _existing_columns(conn) -> set[str]:
    result = conn.execute(text(f"PRAGMA table_info({TABLE})"))
    return {row[1] for row in result.fetchall()}


def main() -> None:
    print(f"Migrando tabela '{TABLE}'...")
    with engine.connect() as conn:
        existing = _existing_columns(conn)
        added = 0
        for col_name, col_type in COLUMNS:
            if col_name in existing:
                print(f"  [ok] '{col_name}' já existe — ignorado.")
            else:
                conn.execute(text(
                    f"ALTER TABLE {TABLE} ADD COLUMN {col_name} {col_type}"
                ))
                conn.commit()
                print(f"  [+]  '{col_name}' ({col_type}) adicionado.")
                added += 1

    if added:
        print(f"\nMigração concluída — {added} coluna(s) adicionada(s).")
    else:
        print("\nNada a migrar — banco já está atualizado.")


if __name__ == "__main__":
    main()
