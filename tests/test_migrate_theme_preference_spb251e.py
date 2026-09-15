from __future__ import annotations

import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from scripts.migrate_add_theme_preference import COLUMN, TABLE, _existing_columns, run_migration


OLD_SCHEMA_SQL = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username VARCHAR(150) NOT NULL UNIQUE,
        email VARCHAR(150) NOT NULL UNIQUE,
        phone VARCHAR(20),
        password_hash VARCHAR(255) NOT NULL,
        is_admin BOOLEAN NOT NULL DEFAULT 0,
        is_subscriber BOOLEAN NOT NULL DEFAULT 0,
        bot_active BOOLEAN NOT NULL DEFAULT 1,
        chat_id VARCHAR(50),
        telegram_link_code VARCHAR(64) UNIQUE,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""


def _make_old_schema_engine():
    """
    SQLite em memória com o schema ANTIGO (sem theme_preference), isolado
    por teste (StaticPool + check_same_thread=False mantém a mesma conexão
    lógica viva pelo tempo de vida do engine). Nunca toca app.db.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text(OLD_SCHEMA_SQL))
        conn.execute(text(
            "INSERT INTO users (username, email, password_hash) "
            "VALUES ('user_a', 'a@example.test', 'hash-a')"
        ))
        conn.execute(text(
            "INSERT INTO users (username, email, password_hash) "
            "VALUES ('user_b', 'b@example.test', 'hash-b')"
        ))
    return engine


class MigrateThemePreferenceSPB251ETest(unittest.TestCase):
    def _old_schema_engine(self):
        engine = _make_old_schema_engine()
        self.addCleanup(engine.dispose)
        return engine

    def test_old_schema_has_no_theme_preference_column(self):
        engine = self._old_schema_engine()
        with engine.connect() as conn:
            self.assertNotIn(COLUMN, _existing_columns(conn))

    def test_adds_theme_preference_column(self):
        engine = self._old_schema_engine()
        added = run_migration(engine)
        self.assertTrue(added)
        with engine.connect() as conn:
            self.assertIn(COLUMN, _existing_columns(conn))

    def test_default_value_is_dark_for_existing_rows(self):
        engine = self._old_schema_engine()
        run_migration(engine)
        with engine.connect() as conn:
            rows = conn.execute(text(f"SELECT username, {COLUMN} FROM {TABLE} ORDER BY username")).fetchall()
        self.assertEqual([(r[0], r[1]) for r in rows], [("user_a", "dark"), ("user_b", "dark")])

    def test_existing_user_data_preserved(self):
        engine = self._old_schema_engine()
        with engine.connect() as conn:
            before = conn.execute(text("SELECT id, username, email, password_hash FROM users ORDER BY id")).fetchall()

        run_migration(engine)

        with engine.connect() as conn:
            after = conn.execute(text("SELECT id, username, email, password_hash FROM users ORDER BY id")).fetchall()
        self.assertEqual(before, after)

    def test_second_run_is_noop(self):
        engine = self._old_schema_engine()
        first = run_migration(engine)
        second = run_migration(engine)
        self.assertTrue(first)
        self.assertFalse(second)

    def test_third_run_is_noop(self):
        engine = self._old_schema_engine()
        run_migration(engine)
        run_migration(engine)
        third = run_migration(engine)
        self.assertFalse(third)

    def test_rerun_does_not_overwrite_existing_value(self):
        engine = self._old_schema_engine()
        run_migration(engine)
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE {TABLE} SET {COLUMN} = 'light' WHERE username = 'user_a'"))

        rerun_added = run_migration(engine)  # deve ser no-op (coluna já existe)

        with engine.connect() as conn:
            value = conn.execute(
                text(f"SELECT {COLUMN} FROM {TABLE} WHERE username = 'user_a'")
            ).scalar_one()
        self.assertFalse(rerun_added)
        self.assertEqual(value, "light")

    def test_column_definition_not_null_with_dark_default(self):
        engine = self._old_schema_engine()
        run_migration(engine)
        with engine.connect() as conn:
            info = conn.execute(text(f"PRAGMA table_info({TABLE})")).fetchall()
        col = next(row for row in info if row[1] == COLUMN)
        # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
        _, _, col_type, notnull, dflt_value, _ = col
        self.assertEqual(notnull, 1)
        self.assertIn("dark", str(dflt_value))
        self.assertIn("VARCHAR", col_type.upper())

    def test_failure_propagates_instead_of_failing_silently(self):
        # Engine apontando para um caminho SQLite inválido/inacessível:
        # run_migration deve deixar a exceção subir (para o chamador decidir
        # o exit code != 0), nunca engolir o erro.
        broken_engine = create_engine("sqlite:////caminho/que/nao/existe/app_teste.db")
        with self.assertRaises(OperationalError):
            run_migration(broken_engine)


if __name__ == "__main__":
    unittest.main()
