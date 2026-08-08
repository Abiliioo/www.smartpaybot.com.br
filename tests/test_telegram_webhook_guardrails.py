from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
import app as app_module
import app.routes.webhook_telegram as webhook_routes
from domain.models import User
from infrastructure.db import Base

_SYNTHETIC_SECRET = "synthetic-webhook-secret"


def _settings_stub(mode: str, secret: str | None = None):
    from unittest.mock import Mock

    return Mock(TELEGRAM_MODE=mode, TELEGRAM_WEBHOOK_SECRET=secret)


class TelegramWebhookGuardrailTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True, expire_on_commit=False)

        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.session_patches = [
            patch.object(app_module, "SessionLocal", self.Session),
            patch.object(webhook_routes, "SessionLocal", self.Session),
        ]
        for session_patch in self.session_patches:
            session_patch.start()
        self.client = self.app.test_client()

        with self.Session() as db:
            self.user = User(
                username="homolog_user",
                email="homolog@example.test",
                password_hash="hash",
                telegram_link_code="link-code-123",
            )
            db.add(self.user)
            db.commit()
            db.refresh(self.user)
            self.user_id = self.user.id

    def tearDown(self) -> None:
        for session_patch in reversed(self.session_patches):
            session_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _post(self, text: str, chat_id: int = 555, headers: dict | None = None):
        payload = {"message": {"text": text, "chat": {"id": chat_id}}}
        return self.client.post("/webhook/telegram", json=payload, headers=headers or {})

    def _user_chat_id(self) -> str | None:
        with self.Session() as db:
            return db.get(User, self.user_id).chat_id

    def test_disabled_returns_503_without_side_effect(self) -> None:
        with patch.object(webhook_routes, "get_settings", return_value=_settings_stub("disabled")), \
             patch.object(webhook_routes, "send_message") as send_mock, \
             patch.object(webhook_routes, "telegram_ready") as ready_mock:
            resp = self._post("/start link-code-123")

        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.get_json(), {"status": "telegram_disabled"})
        send_mock.assert_not_called()
        ready_mock.assert_not_called()
        self.assertIsNone(self._user_chat_id())

    def test_active_secret_absent_returns_403(self) -> None:
        with patch.object(webhook_routes, "get_settings", return_value=_settings_stub("homologation", secret=None)):
            resp = self._post("/start link-code-123")

        self.assertEqual(resp.status_code, 403)
        self.assertIsNone(self._user_chat_id())

    def test_active_secret_incorrect_returns_403(self) -> None:
        with patch.object(
            webhook_routes, "get_settings",
            return_value=_settings_stub("homologation", secret=_SYNTHETIC_SECRET),
        ):
            resp = self._post(
                "/start link-code-123",
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            )

        self.assertEqual(resp.status_code, 403)
        self.assertIsNone(self._user_chat_id())

    def test_active_secret_correct_identity_invalid_returns_503_no_side_effect(self) -> None:
        with patch.object(
            webhook_routes, "get_settings",
            return_value=_settings_stub("homologation", secret=_SYNTHETIC_SECRET),
        ), patch.object(webhook_routes, "telegram_ready", return_value=False), \
           patch.object(webhook_routes, "send_message") as send_mock:
            resp = self._post(
                "/start link-code-123",
                headers={"X-Telegram-Bot-Api-Secret-Token": _SYNTHETIC_SECRET},
            )

        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.get_json(), {"status": "telegram_not_ready"})
        send_mock.assert_not_called()
        self.assertIsNone(self._user_chat_id())

    def test_active_secret_correct_identity_valid_start_flow_works(self) -> None:
        with patch.object(
            webhook_routes, "get_settings",
            return_value=_settings_stub("homologation", secret=_SYNTHETIC_SECRET),
        ), patch.object(webhook_routes, "telegram_ready", return_value=True), \
           patch.object(webhook_routes, "send_message", return_value=True) as send_mock:
            resp = self._post(
                "/start link-code-123",
                headers={"X-Telegram-Bot-Api-Secret-Token": _SYNTHETIC_SECRET},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "linked"})
        self.assertEqual(self._user_chat_id(), "555")
        send_mock.assert_called_once()

    def test_no_secret_or_token_leaks_in_response_or_headers(self) -> None:
        with patch.object(
            webhook_routes, "get_settings",
            return_value=_settings_stub("homologation", secret=_SYNTHETIC_SECRET),
        ):
            resp = self._post("/start link-code-123", headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})

        body = resp.get_data(as_text=True)
        self.assertNotIn(_SYNTHETIC_SECRET, body)


if __name__ == "__main__":
    unittest.main()
