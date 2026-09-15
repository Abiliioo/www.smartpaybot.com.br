#!/usr/bin/env python3
"""
scripts/migrate_add_theme_preference.py

Migração idempotente: adiciona a coluna `theme_preference` à tabela `users`.

Comportamento:
  - Usuários existentes recebem theme_preference = 'dark' por padrão.
  - Pode ser executado mais de uma vez (ou mais) com segurança: se a coluna já
    existir, o script não faz nada e termina com sucesso (exit code 0).
  - Em caso de erro, termina com exit code != 0 e a exceção é reportada em
    stderr — nunca falha silenciosamente.

Responsabilidades (propositalmente separadas):
  - Este script cuida SOMENTE da migração de schema (idempotente, aditiva).
  - Backup do banco é responsabilidade do orquestrador de deploy (ver
    scripts/deploy-production.ps1 / deploy-production-remote.sh), não deste
    script — evita duplicar a responsabilidade e manter duas fontes de
    verdade sobre "quando/como" um backup deve ser feito.

Uso:
    .venv\\Scripts\\python.exe scripts\\migrate_add_theme_preference.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import text
from sqlalchemy.engine import Engine

TABLE = "users"
COLUMN = "theme_preference"

# Tempo (ms) que o SQLite espera por um lock antes de desistir, em vez de
# falhar imediatamente com "database is locked" caso haja escrita
# concorrente (ex.: scheduler) no instante exato da migração.
SQLITE_BUSY_TIMEOUT_MS = 5000


def _existing_columns(conn, table: str = TABLE) -> set[str]:
    result = conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


def run_migration(engine: Engine) -> bool:
    """
    Executa a migração contra o `engine` informado.

    Retorna:
        True  -> coluna foi adicionada nesta execução.
        False -> coluna já existia (no-op idempotente).

    Levanta a exceção original em caso de falha (não a engole) — quem chama
    decide o exit code.
    """
    with engine.connect() as conn:
        conn.execute(text(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}"))

        existing = _existing_columns(conn)
        if COLUMN in existing:
            return False

        conn.execute(text(
            f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} VARCHAR(10) NOT NULL DEFAULT 'dark'"
        ))
        conn.commit()

        # Confirma o resultado real no schema, em vez de assumir que o ALTER
        # funcionou só porque não levantou exceção.
        confirmed = _existing_columns(conn)
        if COLUMN not in confirmed:
            raise RuntimeError(
                f"ALTER TABLE reportou sucesso, mas '{COLUMN}' não aparece em "
                f"PRAGMA table_info({TABLE}) após o commit — schema inconsistente."
            )
        return True


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv()

    from infrastructure.db import engine

    print(f"Migrando tabela '{TABLE}'...")
    try:
        added = run_migration(engine)
    except Exception as exc:  # noqa: BLE001 — reportar qualquer falha, nunca engolir
        print(f"  [erro] migração falhou: {exc}", file=sys.stderr)
        return 1

    if added:
        print(f"  [+] '{COLUMN}' VARCHAR(10) NOT NULL DEFAULT 'dark' adicionado.")
        print("  [+] Todos os usuários existentes ficam com o tema escuro (padrão atual).")
        print("  [+] Confirmado via PRAGMA table_info: coluna presente no schema.")
    else:
        print(f"  [ok] '{COLUMN}' já existe — nada a fazer.")

    print("\nMigração concluída (exit 0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
