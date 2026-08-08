from __future__ import annotations

import contextlib
import importlib
import unittest
import os
from unittest import mock

import app as app_module
import infrastructure.config as config_module
from infrastructure.config import resolve_app_env
from infrastructure.db import validate_database_url


_ENV_KEYS = ("APP_ENV", "FLASK_ENV", "DATABASE_URL", "SECRET_KEY", "SCHEDULER")


@contextlib.contextmanager
def reloaded_settings(**overrides):
    """
    Recarrega infrastructure.config com um ambiente controlado.

    Necessario porque os campos do dataclass Settings usam os.getenv(...)
    diretamente como valor default, e esses defaults sao calculados uma
    UNICA vez, no momento em que a classe e definida (import do modulo) --
    resetar o singleton _settings sozinho nao faz Settings() reler
    variaveis de ambiente novas. O reload forca a reexecucao do corpo da
    classe contra o ambiente controlado por este context manager.

    config.py chama load_dotenv() no proprio import, o que repopularia as
    chaves removidas abaixo a partir do .env real em disco -- por isso
    load_dotenv e neutralizado durante o reload controlado.

    O "finally" sempre restaura o ambiente real e recarrega o modulo de
    volta ao estado real, mesmo se o reload sob teste levantar RuntimeError.
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


class ResolveAppEnvTest(unittest.TestCase):
    """Testes puros -- resolve_app_env recebe argumentos diretos, sem env/reload."""

    def test_development_explicit_is_accepted(self) -> None:
        self.assertEqual(resolve_app_env("development", "development"), "development")

    def test_homologation_explicit_is_accepted(self) -> None:
        self.assertEqual(resolve_app_env("production", "homologation"), "homologation")

    def test_production_explicit_is_accepted(self) -> None:
        self.assertEqual(resolve_app_env("production", "production"), "production")

    def test_invalid_value_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_app_env("development", "staging")

    def test_typo_produciton_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_app_env("development", "produciton")

    def test_absent_with_flask_env_development_derives_development(self) -> None:
        self.assertEqual(resolve_app_env("development", None), "development")
        self.assertEqual(resolve_app_env("development", ""), "development")

    def test_absent_with_flask_env_production_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_app_env("production", None)

    def test_absent_with_flask_env_production_empty_string_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_app_env("production", "")


class SettingsAppEnvIntegrationTest(unittest.TestCase):
    """Integra resolve_app_env com o dataclass Settings via reload controlado."""

    def test_settings_development_default_when_app_env_absent(self) -> None:
        with reloaded_settings(FLASK_ENV="development") as cfg:
            self.assertEqual(cfg.get_settings().APP_ENV, "development")

    def test_settings_homologation_explicit(self) -> None:
        with reloaded_settings(
            FLASK_ENV="production", APP_ENV="homologation", SECRET_KEY="h" * 32
        ) as cfg:
            self.assertEqual(cfg.get_settings().APP_ENV, "homologation")

    def test_settings_production_explicit(self) -> None:
        with reloaded_settings(
            FLASK_ENV="production", APP_ENV="production", SECRET_KEY="p" * 32
        ) as cfg:
            self.assertEqual(cfg.get_settings().APP_ENV, "production")

    def test_settings_production_without_app_env_raises_on_import(self) -> None:
        with self.assertRaises(RuntimeError):
            with reloaded_settings(FLASK_ENV="production"):
                pass  # pragma: no cover - reload ja levanta antes do yield

    def test_settings_invalid_app_env_raises_on_import(self) -> None:
        with self.assertRaises(RuntimeError):
            with reloaded_settings(FLASK_ENV="development", APP_ENV="staging"):
                pass  # pragma: no cover - reload ja levanta antes do yield


class DatabaseUrlWasExplicitTest(unittest.TestCase):
    def test_database_url_was_explicit_true_when_set(self) -> None:
        with reloaded_settings(FLASK_ENV="development", DATABASE_URL="sqlite:///anything.db") as cfg:
            self.assertTrue(cfg.get_settings().DATABASE_URL_WAS_EXPLICIT)

    def test_database_url_was_explicit_false_when_absent(self) -> None:
        with reloaded_settings(FLASK_ENV="development") as cfg:
            settings = cfg.get_settings()
            self.assertFalse(settings.DATABASE_URL_WAS_EXPLICIT)
            self.assertEqual(settings.DATABASE_URL, "sqlite:///app.db")


class ValidateDatabaseUrlTest(unittest.TestCase):
    """Testes puros de infrastructure.db.validate_database_url."""

    def test_homolog_with_relative_homolog_db_is_accepted(self) -> None:
        validate_database_url("homologation", "sqlite:///homolog.db", True)

    def test_homolog_with_absolute_homolog_db_is_accepted(self) -> None:
        validate_database_url(
            "homologation", "sqlite:////var/www/homolog.smartpaybot/homolog.db", True
        )

    def test_homolog_with_app_db_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_database_url("homologation", "sqlite:///app.db", True)

    def test_homolog_with_wrong_filename_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_database_url("homologation", "sqlite:///teste.db", True)

    def test_homolog_with_memory_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_database_url("homologation", "sqlite:///:memory:", True)

    def test_homolog_with_postgres_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_database_url("homologation", "postgresql://user:pass@host/db", True)

    def test_homolog_without_explicit_database_url_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_database_url("homologation", "sqlite:///app.db", False)

    def test_production_keeps_current_database_url_behavior(self) -> None:
        validate_database_url("production", "sqlite:////var/www/smartpaybot/app.db", True)

    def test_development_keeps_fallback_behavior(self) -> None:
        validate_database_url("development", "sqlite:///app.db", False)

    def test_error_message_never_contains_full_postgres_credentials(self) -> None:
        url = "postgresql://admin:supersecret@10.0.0.5/homolog"
        with self.assertRaises(RuntimeError) as ctx:
            validate_database_url("homologation", url, True)
        self.assertNotIn("supersecret", str(ctx.exception))
        self.assertNotIn(url, str(ctx.exception))


class DatabaseUrlGuardrailBeforeCreateEngineTest(unittest.TestCase):
    """
    Prova o achado central da auditoria: o guardrail roda ANTES de
    create_engine(), nunca depois. Recarrega infrastructure.db sob um
    ambiente de homologacao invalido e comprova que create_engine jamais
    e chamado.
    """

    def test_invalid_homolog_database_url_blocks_create_engine(self) -> None:
        import infrastructure.db as db_module

        with reloaded_settings(
            FLASK_ENV="production",
            APP_ENV="homologation",
            DATABASE_URL="sqlite:///app.db",
            SECRET_KEY="h" * 32,
        ):
            with mock.patch("sqlalchemy.create_engine") as mocked_create_engine:
                with self.assertRaises(RuntimeError):
                    importlib.reload(db_module)
                mocked_create_engine.assert_not_called()

        # Restaura infrastructure.db com o ambiente real apos o teste --
        # o reload dentro do "with reloaded_settings" ja restaurou
        # infrastructure.config; aqui garantimos que infrastructure.db
        # (engine/SessionLocal reais) tambem volta a um estado consistente.
        importlib.reload(db_module)


class SecretKeyGuardrailTest(unittest.TestCase):
    """
    create_app() usa get_settings() em runtime (nao em import), entao nao
    e necessario recarregar o modulo 'app' -- apenas infrastructure.config,
    via reloaded_settings.
    """

    def test_production_with_strong_secret_boots(self) -> None:
        with reloaded_settings(FLASK_ENV="production", APP_ENV="production", SECRET_KEY="s" * 32):
            app_module.create_app()

    def test_homologation_with_strong_secret_boots(self) -> None:
        with reloaded_settings(
            FLASK_ENV="production", APP_ENV="homologation", SECRET_KEY="h" * 32
        ):
            app_module.create_app()

    def test_production_with_default_secret_is_rejected(self) -> None:
        with reloaded_settings(FLASK_ENV="production", APP_ENV="production"):
            with self.assertRaises(RuntimeError):
                app_module.create_app()

    def test_homologation_with_default_secret_is_rejected(self) -> None:
        with reloaded_settings(FLASK_ENV="production", APP_ENV="homologation"):
            with self.assertRaises(RuntimeError):
                app_module.create_app()

    def test_development_with_default_secret_still_boots(self) -> None:
        with reloaded_settings(FLASK_ENV="development"):
            app_module.create_app()


class ProductionCompatibilityTest(unittest.TestCase):
    """
    Etapa 19: demonstra que a configuracao real de producao (SCHEDULER=0,
    nao SCHEDULER=1) continua subindo normalmente apos os guardrails.
    """

    def test_production_boots_with_scheduler_disabled(self) -> None:
        with reloaded_settings(
            FLASK_ENV="production",
            APP_ENV="production",
            SECRET_KEY="prod-secret-" + "x" * 20,
            DATABASE_URL="sqlite:////var/www/smartpaybot/app.db",
            SCHEDULER="0",
        ) as cfg:
            settings = cfg.get_settings()
            self.assertFalse(settings.SCHEDULER_ENABLED)
            app_module.create_app()  # nao deve levantar


if __name__ == "__main__":
    unittest.main()
