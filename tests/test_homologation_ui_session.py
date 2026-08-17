from __future__ import annotations

import contextlib
import importlib
import os
import unittest
from unittest import mock

from flask import session

import app as app_module
import infrastructure.config as config_module
from infrastructure.config import session_cookie_name_for_app_env


_ENV_KEYS = (
    "APP_ENV",
    "FLASK_ENV",
    "TELEGRAM_MODE",
    "TELEGRAM_TOKEN",
    "TELEGRAM_EXPECTED_BOT_ID",
    "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_BOT_USERNAME",
    "SECRET_KEY",
    "DATABASE_URL",
)

_SYNTHETIC_SECRET_KEY = "s" * 32
_SYNTHETIC_TELEGRAM_TOKEN = "123456789:synthetic-b4-test-token"
_SYNTHETIC_BOT_ID = "123456789"
_SYNTHETIC_WEBHOOK_SECRET = "synthetic-b4-webhook-secret"


@contextlib.contextmanager
def reloaded_settings(**overrides):
    """
    Mesmo padrao de tests/test_telegram_guardrails.py e
    tests/test_environment_guardrails.py: recarrega infrastructure.config
    com um ambiente controlado, neutralizando load_dotenv() (que
    repopularia as chaves removidas a partir do .env real em disco).
    """
    original = {key: os.environ.get(key) for key in _ENV_KEYS}
    for key in _ENV_KEYS:
        os.environ.pop(key, None)
    os.environ.update(overrides)
    try:
        with mock.patch("dotenv.load_dotenv"):
            importlib.reload(config_module)
        yield config_module
    finally:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
            if original[key] is not None:
                os.environ[key] = original[key]
        importlib.reload(config_module)


def _production_overrides(**extra):
    base = dict(
        FLASK_ENV="production",
        APP_ENV="production",
        SECRET_KEY=_SYNTHETIC_SECRET_KEY,
        TELEGRAM_MODE="production",
        TELEGRAM_EXPECTED_BOT_ID=_SYNTHETIC_BOT_ID,
        TELEGRAM_TOKEN=_SYNTHETIC_TELEGRAM_TOKEN,
        TELEGRAM_WEBHOOK_SECRET=_SYNTHETIC_WEBHOOK_SECRET,
    )
    base.update(extra)
    return base


def _homologation_overrides(**extra):
    base = dict(
        FLASK_ENV="production",
        APP_ENV="homologation",
        SECRET_KEY=_SYNTHETIC_SECRET_KEY,
        TELEGRAM_MODE="homologation",
        TELEGRAM_EXPECTED_BOT_ID=_SYNTHETIC_BOT_ID,
        TELEGRAM_TOKEN=_SYNTHETIC_TELEGRAM_TOKEN,
        TELEGRAM_WEBHOOK_SECRET=_SYNTHETIC_WEBHOOK_SECRET,
    )
    base.update(extra)
    return base


def _development_overrides(**extra):
    base = dict(FLASK_ENV="development")
    base.update(extra)
    return base


def _client_with_session_probe(app):
    """
    Registra uma rota minima que escreve na sessao, para provar o
    Set-Cookie real emitido pelo Flask -- sem depender de login/DB.
    """

    @app.route("/__test_session_probe__")
    def _probe():
        session["probe"] = "1"
        return "ok"

    return app.test_client()


class SessionCookieConfigTest(unittest.TestCase):
    """Secao 12 -- contrato de app.config por APP_ENV."""

    def test_production_cookie_config(self) -> None:
        with reloaded_settings(**_production_overrides()):
            app = app_module.create_app()
            self.assertEqual(app.config["APP_ENV"], "production")
            self.assertEqual(app.config["SESSION_COOKIE_NAME"], "session")
            self.assertIs(app.config["SESSION_COOKIE_SECURE"], True)
            self.assertIs(app.config["SESSION_COOKIE_HTTPONLY"], True)
            self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
            self.assertIsNone(app.config["SESSION_COOKIE_DOMAIN"])
            self.assertEqual(app.config["SESSION_COOKIE_PATH"], "/")

    def test_homologation_cookie_config(self) -> None:
        with reloaded_settings(**_homologation_overrides()):
            app = app_module.create_app()
            self.assertEqual(app.config["APP_ENV"], "homologation")
            self.assertEqual(app.config["SESSION_COOKIE_NAME"], "smartpaybot_homolog_session")
            self.assertIs(app.config["SESSION_COOKIE_SECURE"], True)
            self.assertIs(app.config["SESSION_COOKIE_HTTPONLY"], True)
            self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
            self.assertIsNone(app.config["SESSION_COOKIE_DOMAIN"])
            self.assertEqual(app.config["SESSION_COOKIE_PATH"], "/")

    def test_development_cookie_config(self) -> None:
        with reloaded_settings(**_development_overrides()):
            app = app_module.create_app()
            self.assertEqual(app.config["APP_ENV"], "development")
            self.assertEqual(app.config["SESSION_COOKIE_NAME"], "session")
            self.assertIs(app.config["SESSION_COOKIE_SECURE"], False)
            self.assertIs(app.config["SESSION_COOKIE_HTTPONLY"], True)
            self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
            self.assertIsNone(app.config["SESSION_COOKIE_DOMAIN"])
            self.assertEqual(app.config["SESSION_COOKIE_PATH"], "/")


class SessionCookieHttpTest(unittest.TestCase):
    """Secao 13 -- cookie HTTP real emitido pelo Flask test client."""

    def _set_cookie_header(self, app) -> str:
        client = _client_with_session_probe(app)
        resp = client.get("/__test_session_probe__")
        headers = resp.headers.getlist("Set-Cookie")
        self.assertEqual(len(headers), 1)
        return headers[0]

    def test_production_set_cookie_header(self) -> None:
        with reloaded_settings(**_production_overrides()):
            app = app_module.create_app()
            header = self._set_cookie_header(app)

        self.assertTrue(header.startswith("session="))
        self.assertIn("Secure", header)
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Lax", header)
        self.assertIn("Path=/", header)
        self.assertNotIn("Domain=", header)

    def test_homologation_set_cookie_header(self) -> None:
        with reloaded_settings(**_homologation_overrides()):
            app = app_module.create_app()
            header = self._set_cookie_header(app)

        self.assertTrue(header.startswith("smartpaybot_homolog_session="))
        self.assertFalse(header.startswith("session="))
        self.assertIn("Secure", header)
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Lax", header)
        self.assertIn("Path=/", header)
        self.assertNotIn("Domain=", header)


class BannerRenderingTest(unittest.TestCase):
    """Secao 14 -- banner, marcador visual e <title> condicionados a APP_ENV."""

    def test_homologation_shows_banner_marker_and_title_prefix(self) -> None:
        with reloaded_settings(**_homologation_overrides()):
            app = app_module.create_app()
            client = app.test_client()
            resp = client.get("/auth/login")

        html = resp.get_data(as_text=True)
        self.assertIn("HOMOLOGAÇÃO", html)
        self.assertIn("AMBIENTE DE TESTES", html)
        self.assertIn("env-homologation", html)
        self.assertIn("[HOMOLOGAÇÃO] ", html)

    def test_production_hides_banner_and_marker(self) -> None:
        with reloaded_settings(**_production_overrides()):
            app = app_module.create_app()
            client = app.test_client()
            resp = client.get("/auth/login")

        html = resp.get_data(as_text=True)
        self.assertNotIn("env-banner", html)
        self.assertNotIn("AMBIENTE DE TESTES", html)
        self.assertNotIn("env-homologation", html)
        self.assertNotIn("[HOMOLOGAÇÃO] ", html)

    def test_development_hides_banner_and_marker(self) -> None:
        with reloaded_settings(**_development_overrides()):
            app = app_module.create_app()
            client = app.test_client()
            resp = client.get("/auth/login")

        html = resp.get_data(as_text=True)
        self.assertNotIn("env-banner", html)
        self.assertNotIn("AMBIENTE DE TESTES", html)
        self.assertNotIn("env-homologation", html)
        self.assertNotIn("[HOMOLOGAÇÃO] ", html)


class HostnameDoesNotControlEnvironmentTest(unittest.TestCase):
    """
    Secao 15 -- prova de que APP_ENV, e nao o Host header/hostname, e a
    fonte de verdade para banner e cookie.
    """

    def test_production_with_homolog_host_header_stays_production(self) -> None:
        with reloaded_settings(**_production_overrides()):
            app = app_module.create_app()
            client = _client_with_session_probe(app)

            page = client.get("/auth/login", headers={"Host": "homolog.smartpaybot.com.br"})
            probe = client.get(
                "/__test_session_probe__", headers={"Host": "homolog.smartpaybot.com.br"}
            )

        html = page.get_data(as_text=True)
        self.assertNotIn("AMBIENTE DE TESTES", html)
        self.assertNotIn("env-homologation", html)

        set_cookie = probe.headers.getlist("Set-Cookie")[0]
        self.assertTrue(set_cookie.startswith("session="))

    def test_homologation_with_production_host_header_stays_homologation(self) -> None:
        with reloaded_settings(**_homologation_overrides()):
            app = app_module.create_app()
            client = _client_with_session_probe(app)

            page = client.get("/auth/login", headers={"Host": "smartpaybot.com.br"})
            probe = client.get("/__test_session_probe__", headers={"Host": "smartpaybot.com.br"})

        html = page.get_data(as_text=True)
        self.assertIn("AMBIENTE DE TESTES", html)
        self.assertIn("env-homologation", html)

        set_cookie = probe.headers.getlist("Set-Cookie")[0]
        self.assertTrue(set_cookie.startswith("smartpaybot_homolog_session="))


class SessionCookieNameEnvOverrideIsIgnoredTest(unittest.TestCase):
    """
    Secao 16 -- SESSION_COOKIE_NAME nunca e lido do ambiente. Como
    infrastructure/config.py e app/__init__.py nunca leem essa variavel
    (o nome e derivado puramente de APP_ENV via
    session_cookie_name_for_app_env), um valor sintetico externo nao pode
    alterar o contrato -- este teste documenta essa garantia.
    """

    def test_external_session_cookie_name_env_var_has_no_effect(self) -> None:
        with mock.patch.dict(os.environ, {"SESSION_COOKIE_NAME": "evil_cookie"}):
            with reloaded_settings(**_production_overrides()):
                app = app_module.create_app()

        self.assertEqual(app.config["SESSION_COOKIE_NAME"], "session")
        self.assertNotEqual(app.config["SESSION_COOKIE_NAME"], "evil_cookie")


class SessionCookieNameForAppEnvPureFunctionTest(unittest.TestCase):
    """Testes puros da funcao helper, sem env/reload."""

    def test_production_and_development_share_legacy_cookie_name(self) -> None:
        self.assertEqual(session_cookie_name_for_app_env("production"), "session")
        self.assertEqual(session_cookie_name_for_app_env("development"), "session")

    def test_homologation_has_distinct_cookie_name(self) -> None:
        self.assertEqual(
            session_cookie_name_for_app_env("homologation"),
            "smartpaybot_homolog_session",
        )

    def test_unknown_app_env_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            session_cookie_name_for_app_env("staging")


if __name__ == "__main__":
    unittest.main()
