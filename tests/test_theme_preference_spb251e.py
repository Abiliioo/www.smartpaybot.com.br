from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
import app as app_module
import app.routes.dashboard as dashboard_routes
from app.security import AppUser
from domain.models import User
from infrastructure.db import Base


class ThemePreferenceSPB251ETestBase(unittest.TestCase):
    """
    Base comum: banco em memória isolado (nunca app.db), dois usuários
    (A e B) para os testes de ownership/isolamento.
    """

    WTF_CSRF_ENABLED = False

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True, expire_on_commit=False)

        with self.Session() as db:
            user_a = User(username="theme_a", email="theme_a@example.test", password_hash="hash-a")
            user_b = User(username="theme_b", email="theme_b@example.test", password_hash="hash-b")
            db.add_all([user_a, user_b])
            db.commit()
            db.refresh(user_a)
            db.refresh(user_b)
            self.user_a_id = int(user_a.id)
            self.user_b_id = int(user_b.id)

        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=self.WTF_CSRF_ENABLED)
        self.patches = [
            patch.object(app_module, "SessionLocal", self.Session),
            patch.object(dashboard_routes, "SessionLocal", self.Session),
        ]
        for item in self.patches:
            item.start()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _login(self, user_id: int) -> None:
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def _theme_of(self, user_id: int) -> str:
        with self.Session() as db:
            return db.get(User, user_id).theme_preference


class ThemePreferenceBehaviorTest(ThemePreferenceSPB251ETestBase):
    """CSRF desligado aqui de propósito — isola a lógica de negócio da rota
    (allowlist, persistência, ownership) da checagem de CSRF, que tem seu
    próprio teste dedicado em ThemePreferenceCsrfTest."""

    def test_default_is_dark_for_new_user(self) -> None:
        self.assertEqual(self._theme_of(self.user_a_id), "dark")
        self.assertEqual(self._theme_of(self.user_b_id), "dark")

    def test_default_dark_reflected_in_ssr_html(self) -> None:
        self._login(self.user_a_id)
        html = self.client.get("/dashboard/").get_data(as_text=True)
        self.assertIn('data-theme="dark"', html)

    def test_post_light_persists(self) -> None:
        self._login(self.user_a_id)
        resp = self.client.post("/dashboard/theme", json={"theme": "light"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"ok": True, "theme": "light"})
        self.assertEqual(self._theme_of(self.user_a_id), "light")

    def test_post_dark_persists(self) -> None:
        self._login(self.user_a_id)
        self.client.post("/dashboard/theme", json={"theme": "light"})
        resp = self.client.post("/dashboard/theme", json={"theme": "dark"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._theme_of(self.user_a_id), "dark")

    def test_invalid_theme_rejected_with_400(self) -> None:
        self._login(self.user_a_id)
        resp = self.client.post("/dashboard/theme", json={"theme": "blue"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "invalid_theme"})

    def test_invalid_theme_does_not_change_current_value(self) -> None:
        self._login(self.user_a_id)
        self.client.post("/dashboard/theme", json={"theme": "light"})
        self.client.post("/dashboard/theme", json={"theme": "blue"})  # rejeitado
        self.assertEqual(self._theme_of(self.user_a_id), "light")

    def test_missing_theme_field_rejected_with_400(self) -> None:
        self._login(self.user_a_id)
        resp = self.client.post("/dashboard/theme", json={})
        self.assertEqual(resp.status_code, 400)

    def test_user_a_cannot_change_user_b_theme(self) -> None:
        self._login(self.user_a_id)
        self.client.post("/dashboard/theme", json={"theme": "light"})
        self.assertEqual(self._theme_of(self.user_a_id), "light")
        self.assertEqual(self._theme_of(self.user_b_id), "dark")

    def test_payload_user_id_is_ignored_ownership_cannot_be_spoofed(self) -> None:
        # Mesmo que o payload tente "apontar" para outro usuario, a rota so
        # le o id da sessao autenticada (current_user.id) -- nunca do body.
        self._login(self.user_a_id)
        resp = self.client.post(
            "/dashboard/theme",
            json={"theme": "light", "user_id": self.user_b_id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._theme_of(self.user_a_id), "light")
        self.assertEqual(self._theme_of(self.user_b_id), "dark")

    def test_unauthenticated_request_is_rejected(self) -> None:
        resp = self.client.post("/dashboard/theme", json={"theme": "light"})
        self.assertIn(resp.status_code, (302, 401))
        self.assertEqual(self._theme_of(self.user_a_id), "dark")

    def test_next_request_renders_persisted_theme(self) -> None:
        self._login(self.user_a_id)
        self.client.post("/dashboard/theme", json={"theme": "light"})
        html = self.client.get("/dashboard/").get_data(as_text=True)
        self.assertIn('data-theme="light"', html)

    def test_app_user_exposes_theme_preference(self) -> None:
        with self.Session() as db:
            user = db.get(User, self.user_a_id)
            app_user = AppUser.from_domain(user)
        self.assertEqual(app_user.theme_preference, "dark")

    def test_app_user_default_fallback_is_dark(self) -> None:
        app_user = AppUser(user_id=999, username="sem-theme")
        self.assertEqual(app_user.theme_preference, "dark")

    def test_legacy_row_inserted_without_explicit_theme_gets_dark_via_server_default(self) -> None:
        # Simula uma linha inserida por SQL cru (sem passar pelo ORM/Python
        # default) -- o valor precisa vir do server_default da coluna.
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (username, email, password_hash, is_admin, is_subscriber) "
                "VALUES ('legacy_user', 'legacy@example.test', 'hash-legacy', 0, 0)"
            ))
        with self.Session() as db:
            legacy = db.query(User).filter_by(username="legacy_user").one()
            self.assertEqual(legacy.theme_preference, "dark")


class ThemePreferenceCsrfTest(ThemePreferenceSPB251ETestBase):
    WTF_CSRF_ENABLED = True

    def test_post_without_csrf_token_is_rejected(self) -> None:
        self._login(self.user_a_id)
        resp = self.client.post("/dashboard/theme", json={"theme": "light"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._theme_of(self.user_a_id), "dark")


if __name__ == "__main__":
    unittest.main()
