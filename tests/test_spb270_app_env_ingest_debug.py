from __future__ import annotations

import contextlib
import importlib
import os
import types
import unittest
from unittest import mock

from flask import Flask

import app.routes.ingest as ingest_module
import infrastructure.config as config_module


_ENV_KEYS = (
    "APP_ENV",
    "DEBUG",
    "FLASK_ENV",
    "SECRET_KEY",
    "TELEGRAM_EXPECTED_BOT_ID",
    "TELEGRAM_MODE",
)

_BOT_ID = "123"


@contextlib.contextmanager
def controlled_config(**overrides):
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
        with mock.patch("dotenv.load_dotenv"):
            importlib.reload(config_module)


def _required_env(app_env: str) -> dict[str, str]:
    if app_env == "development":
        return {"APP_ENV": "development"}
    return {
        "APP_ENV": app_env,
        "SECRET_KEY": f"{app_env}-secret-" + "x" * 32,
        "TELEGRAM_MODE": app_env,
        "TELEGRAM_EXPECTED_BOT_ID": _BOT_ID,
    }


class DebugByAppEnvTest(unittest.TestCase):
    def test_development_without_debug_defaults_true(self) -> None:
        with controlled_config(FLASK_ENV="development", **_required_env("development")) as cfg:
            self.assertTrue(cfg.get_settings().DEBUG)

    def test_development_with_debug_false_is_false(self) -> None:
        with controlled_config(
            FLASK_ENV="development", DEBUG="false", **_required_env("development")
        ) as cfg:
            self.assertFalse(cfg.get_settings().DEBUG)

    def test_homologation_without_debug_defaults_false(self) -> None:
        with controlled_config(
            FLASK_ENV="production", **_required_env("homologation")
        ) as cfg:
            self.assertFalse(cfg.get_settings().DEBUG)

    def test_production_without_debug_defaults_false(self) -> None:
        with controlled_config(FLASK_ENV="production", **_required_env("production")) as cfg:
            self.assertFalse(cfg.get_settings().DEBUG)

    def test_homologation_with_debug_true_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            with controlled_config(
                FLASK_ENV="production", DEBUG="true", **_required_env("homologation")
            ):
                pass

    def test_production_with_debug_true_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            with controlled_config(
                FLASK_ENV="production", DEBUG="true", **_required_env("production")
            ):
                pass

    def test_flask_env_development_with_app_env_production_defaults_debug_false(self) -> None:
        with controlled_config(
            FLASK_ENV="development", **_required_env("production")
        ) as cfg:
            settings = cfg.get_settings()
            self.assertEqual(settings.APP_ENV, "production")
            self.assertFalse(settings.DEBUG)

    def test_flask_env_production_with_app_env_development_defaults_debug_true(self) -> None:
        with controlled_config(
            FLASK_ENV="production", **_required_env("development")
        ) as cfg:
            settings = cfg.get_settings()
            self.assertEqual(settings.APP_ENV, "development")
            self.assertTrue(settings.DEBUG)


class IngestTokenByAppEnvTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        ingest_module._no_token_warned = False

    def tearDown(self) -> None:
        ingest_module._no_token_warned = False

    def _check(self, app_env: str, token: str | None, header: str | None = None) -> bool:
        headers = {}
        if header is not None:
            headers["X-Internal-Ingest-Token"] = header
        settings = types.SimpleNamespace(
            APP_ENV=app_env,
            FLASK_ENV="development",
            INTERNAL_INGEST_TOKEN=token,
        )
        with self.app.test_request_context(headers=headers):
            with mock.patch.object(ingest_module, "get_settings", return_value=settings):
                return ingest_module._check_token()

    def test_development_without_configured_token_allows_request(self) -> None:
        self.assertTrue(self._check("development", None))

    def test_development_with_configured_token_rejects_missing_header(self) -> None:
        self.assertFalse(self._check("development", "test-token"))

    def test_homologation_without_configured_token_rejects_request(self) -> None:
        self.assertFalse(self._check("homologation", None))

    def test_production_without_configured_token_rejects_request(self) -> None:
        self.assertFalse(self._check("production", None))

    def test_homologation_with_correct_token_allows_request(self) -> None:
        self.assertTrue(self._check("homologation", "test-token", "test-token"))

    def test_production_with_correct_token_allows_request(self) -> None:
        self.assertTrue(self._check("production", "test-token", "test-token"))

    def test_flask_env_development_with_app_env_homologation_without_token_rejects(self) -> None:
        self.assertFalse(self._check("homologation", None))

    def test_flask_env_development_with_app_env_production_without_token_rejects(self) -> None:
        self.assertFalse(self._check("production", None))


if __name__ == "__main__":
    unittest.main()
