from __future__ import annotations

import contextlib
import hashlib
import importlib
import logging
import os
import socket
import unittest
from unittest import mock

import infrastructure.config as config_module
import infrastructure.telegram as telegram_module
from infrastructure.config import resolve_telegram_expected_bot_id, resolve_telegram_mode
from infrastructure.telegram import TelegramGuardError


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

_SYNTHETIC_TOKEN = "123456789:synthetic-test-token"
_SYNTHETIC_TOKEN_B = "987654321:another-synthetic-token"
_SYNTHETIC_SECRET = "synthetic-webhook-secret"
_SYNTHETIC_BOT_ID = 123456789


@contextlib.contextmanager
def reloaded_settings(**overrides):
    """
    Recarrega infrastructure.config com um ambiente controlado, neutralizando
    load_dotenv() (que roda no import do modulo e repopularia as chaves
    removidas a partir do .env real em disco). Ver tests/test_environment_guardrails.py
    para o mesmo padrao aplicado a APP_ENV/DATABASE_URL/SECRET_KEY.
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


def _settings_stub(**overrides):
    """SimpleNamespace-like stub minimo para mockar get_settings() em infrastructure.telegram."""
    base = {
        "TELEGRAM_MODE": "homologation",
        "TELEGRAM_TOKEN": _SYNTHETIC_TOKEN,
        "TELEGRAM_EXPECTED_BOT_ID": _SYNTHETIC_BOT_ID,
        "TELEGRAM_WEBHOOK_SECRET": _SYNTHETIC_SECRET,
    }
    base.update(overrides)
    return mock.Mock(**base)


def _get_me_response(status_code=200, ok=True, bot_id=_SYNTHETIC_BOT_ID, is_bot=True, malformed=False):
    resp = mock.Mock()
    resp.status_code = status_code
    if malformed:
        resp.json.side_effect = ValueError("invalid json")
    else:
        resp.json.return_value = {"ok": ok, "result": {"id": bot_id, "is_bot": is_bot}}
    return resp


class ResolveTelegramModeMatrixTest(unittest.TestCase):
    """Testes puros -- resolve_telegram_mode recebe argumentos diretos, sem env/reload."""

    def test_development_absent_is_disabled(self) -> None:
        self.assertEqual(resolve_telegram_mode("development", None), "disabled")
        self.assertEqual(resolve_telegram_mode("development", ""), "disabled")

    def test_development_disabled_is_accepted(self) -> None:
        self.assertEqual(resolve_telegram_mode("development", "disabled"), "disabled")

    def test_development_homologation_is_accepted(self) -> None:
        self.assertEqual(resolve_telegram_mode("development", "homologation"), "homologation")

    def test_development_production_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_mode("development", "production")

    def test_homologation_absent_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_mode("homologation", None)

    def test_homologation_disabled_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_mode("homologation", "disabled")

    def test_homologation_homologation_is_accepted(self) -> None:
        self.assertEqual(resolve_telegram_mode("homologation", "homologation"), "homologation")

    def test_homologation_production_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_mode("homologation", "production")

    def test_production_absent_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_mode("production", None)

    def test_production_disabled_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_mode("production", "disabled")

    def test_production_homologation_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_mode("production", "homologation")

    def test_production_production_is_accepted(self) -> None:
        self.assertEqual(resolve_telegram_mode("production", "production"), "production")

    def test_unknown_value_is_rejected_in_every_app_env(self) -> None:
        for app_env in ("development", "homologation", "production"):
            with self.assertRaises(RuntimeError):
                resolve_telegram_mode(app_env, "staging")


class ResolveTelegramExpectedBotIdTest(unittest.TestCase):
    """Testes puros -- Etapa 11.2."""

    def test_disabled_does_not_require_id(self) -> None:
        self.assertIsNone(resolve_telegram_expected_bot_id("disabled", None))
        self.assertIsNone(resolve_telegram_expected_bot_id("disabled", ""))

    def test_active_absent_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_expected_bot_id("homologation", None)

    def test_active_empty_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_expected_bot_id("production", "   ")

    def test_active_non_numeric_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_expected_bot_id("homologation", "abc123")

    def test_active_zero_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_expected_bot_id("production", "0")

    def test_active_negative_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_telegram_expected_bot_id("homologation", "-5")

    def test_active_positive_id_is_accepted(self) -> None:
        self.assertEqual(resolve_telegram_expected_bot_id("production", "123456789"), 123456789)


class SettingsTelegramIntegrationTest(unittest.TestCase):
    """Integra resolve_telegram_mode/expected_bot_id com o dataclass Settings via reload."""

    def test_production_config_completa_sintetica_boot_permitido(self) -> None:
        with reloaded_settings(
            FLASK_ENV="production",
            APP_ENV="production",
            SECRET_KEY="s" * 32,
            TELEGRAM_MODE="production",
            TELEGRAM_EXPECTED_BOT_ID=str(_SYNTHETIC_BOT_ID),
        ) as cfg:
            settings = cfg.get_settings()
            self.assertEqual(settings.TELEGRAM_MODE, "production")
            self.assertEqual(settings.TELEGRAM_EXPECTED_BOT_ID, _SYNTHETIC_BOT_ID)

    def test_homologation_config_completa_sintetica_boot_permitido(self) -> None:
        with reloaded_settings(
            FLASK_ENV="production",
            APP_ENV="homologation",
            SECRET_KEY="h" * 32,
            TELEGRAM_MODE="homologation",
            TELEGRAM_EXPECTED_BOT_ID=str(_SYNTHETIC_BOT_ID),
        ) as cfg:
            settings = cfg.get_settings()
            self.assertEqual(settings.TELEGRAM_MODE, "homologation")
            self.assertEqual(settings.TELEGRAM_EXPECTED_BOT_ID, _SYNTHETIC_BOT_ID)

    def test_production_expected_bot_id_ausente_recusa_boot(self) -> None:
        with self.assertRaises(RuntimeError):
            with reloaded_settings(
                FLASK_ENV="production",
                APP_ENV="production",
                SECRET_KEY="s" * 32,
                TELEGRAM_MODE="production",
            ):
                pass  # pragma: no cover - reload ja levanta antes do yield

    def test_homologation_expected_bot_id_ausente_recusa_boot(self) -> None:
        with self.assertRaises(RuntimeError):
            with reloaded_settings(
                FLASK_ENV="production",
                APP_ENV="homologation",
                SECRET_KEY="h" * 32,
                TELEGRAM_MODE="homologation",
            ):
                pass  # pragma: no cover


class AppStartupTelegramConfigTest(unittest.TestCase):
    """
    Etapa 11.3 -- validacao de configuracao ativa em app/__init__.py:create_app().
    create_app() usa get_settings() em runtime, entao basta controlar
    infrastructure.config via reloaded_settings (nao e necessario recarregar
    o modulo 'app').
    """

    def test_production_token_ausente_boot_recusado(self) -> None:
        import app as app_module

        with reloaded_settings(
            FLASK_ENV="production",
            APP_ENV="production",
            SECRET_KEY="s" * 32,
            TELEGRAM_MODE="production",
            TELEGRAM_EXPECTED_BOT_ID=str(_SYNTHETIC_BOT_ID),
        ):
            # TELEGRAM_TOKEN deliberadamente ausente (nao passado em
            # overrides, e _ENV_KEYS garante que nenhum valor real do
            # ambiente vaze para dentro do reload) -- o motivo da recusa
            # deve ser especificamente TELEGRAM_TOKEN, nao outra chave.
            with self.assertRaises(RuntimeError) as ctx:
                app_module.create_app()
            self.assertIn("TELEGRAM_TOKEN", str(ctx.exception))

    def test_production_webhook_secret_ausente_boot_recusado(self) -> None:
        import app as app_module

        with reloaded_settings(
            FLASK_ENV="production",
            APP_ENV="production",
            SECRET_KEY="s" * 32,
            TELEGRAM_MODE="production",
            TELEGRAM_EXPECTED_BOT_ID=str(_SYNTHETIC_BOT_ID),
            TELEGRAM_TOKEN=_SYNTHETIC_TOKEN,
        ):
            # TELEGRAM_TOKEN fornecido diretamente ao reload (via
            # overrides, antes do reload do modulo -- diferente de
            # mock.patch.dict apos o reload, que nao afeta o default do
            # dataclass ja calculado). TELEGRAM_WEBHOOK_SECRET
            # deliberadamente ausente: deve ser o unico motivo da recusa.
            with self.assertRaises(RuntimeError) as ctx:
                app_module.create_app()
            self.assertIn("TELEGRAM_WEBHOOK_SECRET", str(ctx.exception))

    def test_homologation_expected_id_ausente_recusado(self) -> None:
        # A ausencia de TELEGRAM_EXPECTED_BOT_ID ja e recusada uma camada
        # antes de create_app(): resolve_telegram_expected_bot_id() levanta
        # RuntimeError durante a propria construcao de Settings() (defesa
        # em profundidade -- ainda mais cedo do que o boot do Flask).
        with self.assertRaises(RuntimeError):
            with reloaded_settings(
                FLASK_ENV="production",
                APP_ENV="homologation",
                SECRET_KEY="h" * 32,
                TELEGRAM_MODE="homologation",
            ):
                pass  # pragma: no cover - reload ja levanta antes do yield

    def test_development_homologation_mode_sem_webhook_secret_boot_permitido(self) -> None:
        import app as app_module

        with reloaded_settings(
            FLASK_ENV="development",
            TELEGRAM_MODE="homologation",
            TELEGRAM_EXPECTED_BOT_ID=str(_SYNTHETIC_BOT_ID),
            TELEGRAM_TOKEN=_SYNTHETIC_TOKEN,
        ):
            app_module.create_app()  # nao deve levantar

    def test_disabled_mode_skips_telegram_config_check(self) -> None:
        import app as app_module

        with reloaded_settings(FLASK_ENV="development"):
            app_module.create_app()  # TELEGRAM_MODE=disabled -- nao exige nada

    def test_real_environment_does_not_contaminate_controlled_reload(self) -> None:
        """
        Reproduz o cenario exato encontrado na VPS: valores sinteticos
        "de producao real" presentes em os.environ (simulando um .env real
        ja carregado por load_dotenv() no import inicial do processo), sem
        serem passados como overrides para reloaded_settings(). O reload
        controlado deve ignorar esses valores ambientais -- prova de que
        um .env/os.environ externo nao pode contaminar o teste controlado.
        """
        import app as app_module

        with mock.patch.dict(
            os.environ,
            {
                "TELEGRAM_TOKEN": "synthetic-real-env-token",
                "TELEGRAM_WEBHOOK_SECRET": "synthetic-real-env-secret",
            },
        ):
            with reloaded_settings(
                APP_ENV="production",
                FLASK_ENV="production",
                SECRET_KEY="s" * 32,
                TELEGRAM_MODE="production",
                TELEGRAM_EXPECTED_BOT_ID=str(_SYNTHETIC_BOT_ID),
            ) as cfg:
                settings = cfg.get_settings()
                self.assertFalse(settings.TELEGRAM_TOKEN)
                self.assertFalse(settings.TELEGRAM_WEBHOOK_SECRET)
                with self.assertRaises(RuntimeError) as ctx:
                    app_module.create_app()
                self.assertIn("TELEGRAM_TOKEN", str(ctx.exception))


class TelegramIdentityGuardTest(unittest.TestCase):
    """Etapa 11.4 -- getMe lazy/cacheado."""

    def setUp(self) -> None:
        telegram_module._validated_token_fingerprints.clear()

    def tearDown(self) -> None:
        telegram_module._validated_token_fingerprints.clear()

    def test_getme_called_before_real_operation(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response()) as get_mock, \
             mock.patch("requests.post") as post_mock:
            post_mock.return_value = mock.Mock(status_code=200)
            ok = telegram_module.send_message("chat-1", "hello")

        self.assertTrue(ok)
        get_mock.assert_called_once()  # getMe
        post_mock.assert_called_once()  # sendMessage

    def test_correct_id_and_is_bot_allows_operation(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(bot_id=_SYNTHETIC_BOT_ID, is_bot=True)):
            self.assertTrue(telegram_module.telegram_ready())

    def test_wrong_bot_id_blocks_and_never_calls_real_operation(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(bot_id=999999999)), \
             mock.patch("requests.post") as post_mock:
            ok = telegram_module.send_message("chat-1", "hello")

        self.assertFalse(ok)
        post_mock.assert_not_called()

    def test_is_bot_false_blocks_and_never_calls_real_operation(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(is_bot=False)), \
             mock.patch("requests.post") as post_mock:
            ok = telegram_module.send_message("chat-1", "hello")

        self.assertFalse(ok)
        post_mock.assert_not_called()

    def test_http_non_200_on_getme_blocks(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(status_code=500)):
            self.assertFalse(telegram_module.telegram_ready())

    def test_invalid_json_on_getme_blocks(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(malformed=True)):
            self.assertFalse(telegram_module.telegram_ready())

    def test_ok_false_on_getme_blocks(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(ok=False)):
            self.assertFalse(telegram_module.telegram_ready())

    def test_network_exception_on_getme_blocks(self) -> None:
        import requests
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", side_effect=requests.exceptions.Timeout("boom")):
            self.assertFalse(telegram_module.telegram_ready())


    def test_getme_uses_ipv4_preference_during_request(self) -> None:
        seen_families = []

        def fake_get(*args, **kwargs):
            seen_families.append(telegram_module.urllib3_connection.allowed_gai_family())
            return _get_me_response()

        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", side_effect=fake_get):
            self.assertTrue(telegram_module.telegram_ready())

        self.assertEqual(seen_families, [socket.AF_INET])

    def test_ipv4_preference_is_restored_after_getme_success(self) -> None:
        original_allowed_gai_family = telegram_module.urllib3_connection.allowed_gai_family

        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response()):
            self.assertTrue(telegram_module.telegram_ready())

        self.assertIs(telegram_module.urllib3_connection.allowed_gai_family, original_allowed_gai_family)

    def test_ipv4_preference_is_restored_after_getme_exception(self) -> None:
        import requests

        original_allowed_gai_family = telegram_module.urllib3_connection.allowed_gai_family

        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", side_effect=requests.exceptions.Timeout("boom")):
            self.assertFalse(telegram_module.telegram_ready())

        self.assertIs(telegram_module.urllib3_connection.allowed_gai_family, original_allowed_gai_family)
        self.assertEqual(telegram_module._validated_token_fingerprints, set())

    def test_network_exception_on_getme_is_not_cached_as_success(self) -> None:
        import requests

        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", side_effect=requests.exceptions.Timeout("boom")) as get_mock:
            self.assertFalse(telegram_module.telegram_ready())
            self.assertFalse(telegram_module.telegram_ready())

        self.assertEqual(get_mock.call_count, 2)
    def test_failure_is_not_cached_as_success(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(status_code=500)) as get_mock:
            self.assertFalse(telegram_module.telegram_ready())
            self.assertFalse(telegram_module.telegram_ready())

        # getMe foi tentado nas DUAS chamadas -- falha nao ficou em cache.
        self.assertEqual(get_mock.call_count, 2)

    def test_second_operation_after_success_does_not_repeat_getme(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response()) as get_mock:
            self.assertTrue(telegram_module.telegram_ready())
            self.assertTrue(telegram_module.telegram_ready())

        get_mock.assert_called_once()

    def test_explicit_different_token_requires_new_validation(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response()) as get_mock:
            self.assertTrue(telegram_module.telegram_ready())
            self.assertTrue(telegram_module.telegram_ready(token=_SYNTHETIC_TOKEN_B))

        self.assertEqual(get_mock.call_count, 2)


class AllOperationsRespectGuardTest(unittest.TestCase):
    """Etapa 11.5 -- send_message, get_webhook_info, set_webhook, delete_webhook, get_updates."""

    def setUp(self) -> None:
        telegram_module._validated_token_fingerprints.clear()

    def tearDown(self) -> None:
        telegram_module._validated_token_fingerprints.clear()

    def test_disabled_mode_no_operation_touches_requests(self) -> None:
        disabled_settings = _settings_stub(TELEGRAM_MODE="disabled")
        with mock.patch.object(telegram_module, "get_settings", return_value=disabled_settings), \
             mock.patch("requests.get") as get_mock, mock.patch("requests.post") as post_mock:
            self.assertFalse(telegram_module.send_message("chat-1", "x"))
            self.assertIsNone(telegram_module.get_webhook_info())
            self.assertFalse(telegram_module.set_webhook("https://example.test/webhook"))
            self.assertFalse(telegram_module.delete_webhook())
            self.assertIsNone(telegram_module.get_updates())

        get_mock.assert_not_called()
        post_mock.assert_not_called()

    def _ready_context(self):
        return (
            mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()),
            mock.patch("requests.get", return_value=_get_me_response()),
        )

    def test_get_webhook_info_guarded_before_real_call(self) -> None:
        get_settings_patch, getme_patch = self._ready_context()
        with get_settings_patch, getme_patch as get_mock:
            # segunda chamada de requests.get sera a operacao real; a
            # primeira e o getMe do guard. Usamos side_effect para
            # diferenciar.
            get_mock.side_effect = [
                _get_me_response(),
                mock.Mock(json=mock.Mock(return_value={"ok": True, "result": {"url": ""}})),
            ]
            info = telegram_module.get_webhook_info()

        self.assertEqual(info, {"ok": True, "result": {"url": ""}})
        self.assertEqual(get_mock.call_count, 2)


    def test_get_webhook_info_uses_ipv4_preference_for_readiness_gets(self) -> None:
        seen_families = []

        def fake_get(*args, **kwargs):
            seen_families.append(telegram_module.urllib3_connection.allowed_gai_family())
            if len(seen_families) == 1:
                return _get_me_response()
            return mock.Mock(json=mock.Mock(return_value={"ok": True, "result": {"url": ""}}))

        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", side_effect=fake_get):
            info = telegram_module.get_webhook_info()

        self.assertEqual(info, {"ok": True, "result": {"url": ""}})
        self.assertEqual(seen_families, [socket.AF_INET, socket.AF_INET])

    def test_getme_failure_blocks_get_webhook_info_before_real_call(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(status_code=403)) as get_mock:
            self.assertIsNone(telegram_module.get_webhook_info())

        get_mock.assert_called_once()
    def test_set_webhook_guarded_before_real_call(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response()), \
             mock.patch("requests.post") as post_mock:
            post_mock.return_value = mock.Mock(ok=True, json=mock.Mock(return_value={"ok": True}))
            ok = telegram_module.set_webhook("https://example.test/webhook")

        self.assertTrue(ok)
        post_mock.assert_called_once()

    def test_set_webhook_blocked_never_calls_real_post(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(bot_id=1)), \
             mock.patch("requests.post") as post_mock:
            ok = telegram_module.set_webhook("https://example.test/webhook")

        self.assertFalse(ok)
        post_mock.assert_not_called()

    def test_delete_webhook_guarded_before_real_call(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response()), \
             mock.patch("requests.post") as post_mock:
            post_mock.return_value = mock.Mock(ok=True, json=mock.Mock(return_value={"ok": True}))
            ok = telegram_module.delete_webhook()

        self.assertTrue(ok)
        post_mock.assert_called_once()

    def test_delete_webhook_blocked_never_calls_real_post(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get", return_value=_get_me_response(is_bot=False)), \
             mock.patch("requests.post") as post_mock:
            ok = telegram_module.delete_webhook()

        self.assertFalse(ok)
        post_mock.assert_not_called()

    def test_get_updates_guarded_before_real_call(self) -> None:
        get_settings_patch, _ = self._ready_context()
        with get_settings_patch, mock.patch("requests.get") as get_mock:
            get_mock.side_effect = [
                _get_me_response(),
                mock.Mock(json=mock.Mock(return_value={"ok": True, "result": []})),
            ]
            data = telegram_module.get_updates(offset=1)

        self.assertEqual(data, {"ok": True, "result": []})
        self.assertEqual(get_mock.call_count, 2)

    def test_get_updates_blocked_never_calls_real_get_updates(self) -> None:
        with mock.patch.object(telegram_module, "get_settings", return_value=_settings_stub()), \
             mock.patch("requests.get") as get_mock:
            get_mock.return_value = _get_me_response(status_code=403)
            data = telegram_module.get_updates(offset=1)

        self.assertIsNone(data)
        get_mock.assert_called_once()  # so o getMe (que falhou), nunca o getUpdates real


class SetWebhookSecretHandlingTest(unittest.TestCase):
    """
    Etapa 5 da auditoria forense: set_webhook() nunca pode registrar um
    webhook sem secret. O secret enviado ao Telegram e sempre
    settings.TELEGRAM_WEBHOOK_SECRET -- nao depende do chamador passar o
    valor certo.
    """

    def setUp(self) -> None:
        telegram_module._validated_token_fingerprints.clear()

    def tearDown(self) -> None:
        telegram_module._validated_token_fingerprints.clear()

    def test_production_sends_configured_secret_automatically(self) -> None:
        settings = _settings_stub(TELEGRAM_MODE="production", TELEGRAM_WEBHOOK_SECRET=_SYNTHETIC_SECRET)
        with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
             mock.patch("requests.get", return_value=_get_me_response()), \
             mock.patch("requests.post") as post_mock:
            post_mock.return_value = mock.Mock(ok=True, json=mock.Mock(return_value={"ok": True}))
            ok = telegram_module.set_webhook("https://example.test/webhook")

        self.assertTrue(ok)
        sent_data = post_mock.call_args.kwargs["data"]
        self.assertEqual(sent_data["secret_token"], _SYNTHETIC_SECRET)

    def test_homologation_sends_configured_secret_automatically(self) -> None:
        settings = _settings_stub(TELEGRAM_MODE="homologation", TELEGRAM_WEBHOOK_SECRET=_SYNTHETIC_SECRET)
        with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
             mock.patch("requests.get", return_value=_get_me_response()), \
             mock.patch("requests.post") as post_mock:
            post_mock.return_value = mock.Mock(ok=True, json=mock.Mock(return_value={"ok": True}))
            ok = telegram_module.set_webhook("https://example.test/webhook")

        self.assertTrue(ok)
        sent_data = post_mock.call_args.kwargs["data"]
        self.assertEqual(sent_data["secret_token"], _SYNTHETIC_SECRET)

    def test_caller_passing_matching_secret_still_sends_configured_value(self) -> None:
        settings = _settings_stub(TELEGRAM_WEBHOOK_SECRET=_SYNTHETIC_SECRET)
        with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
             mock.patch("requests.get", return_value=_get_me_response()), \
             mock.patch("requests.post") as post_mock:
            post_mock.return_value = mock.Mock(ok=True, json=mock.Mock(return_value={"ok": True}))
            ok = telegram_module.set_webhook("https://example.test/webhook", secret_token=_SYNTHETIC_SECRET)

        self.assertTrue(ok)
        sent_data = post_mock.call_args.kwargs["data"]
        self.assertEqual(sent_data["secret_token"], _SYNTHETIC_SECRET)

    def test_active_mode_without_configured_secret_blocks_before_requests(self) -> None:
        settings = _settings_stub(TELEGRAM_WEBHOOK_SECRET=None)
        with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
             mock.patch("requests.get", return_value=_get_me_response()), \
             mock.patch("requests.post") as post_mock:
            ok = telegram_module.set_webhook("https://example.test/webhook")

        self.assertFalse(ok)
        post_mock.assert_not_called()

    def test_divergent_explicit_secret_blocks_before_requests(self) -> None:
        settings = _settings_stub(TELEGRAM_WEBHOOK_SECRET=_SYNTHETIC_SECRET)
        with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
             mock.patch("requests.get", return_value=_get_me_response()), \
             mock.patch("requests.post") as post_mock:
            ok = telegram_module.set_webhook(
                "https://example.test/webhook", secret_token="different-value-not-configured"
            )

        self.assertFalse(ok)
        post_mock.assert_not_called()

    def test_disabled_mode_set_webhook_touches_no_network(self) -> None:
        settings = _settings_stub(TELEGRAM_MODE="disabled")
        with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
             mock.patch("requests.get") as get_mock, mock.patch("requests.post") as post_mock:
            ok = telegram_module.set_webhook("https://example.test/webhook")

        self.assertFalse(ok)
        get_mock.assert_not_called()
        post_mock.assert_not_called()

    def test_secret_never_appears_in_logs(self) -> None:
        settings = _settings_stub(TELEGRAM_WEBHOOK_SECRET=None)
        with self.assertLogs("infrastructure.telegram", level="WARNING") as captured:
            with mock.patch.object(telegram_module, "get_settings", return_value=settings):
                telegram_module.set_webhook("https://example.test/webhook", secret_token="some-value")
        full_log = "\n".join(captured.output)
        self.assertNotIn(_SYNTHETIC_SECRET, full_log)
        self.assertNotIn("some-value", full_log)


class LoggingDoesNotLeakSecretsTest(unittest.TestCase):
    """Etapa 13 -- nenhum token/secret aparece em log, nem em RequestException."""

    def setUp(self) -> None:
        telegram_module._validated_token_fingerprints.clear()

    def tearDown(self) -> None:
        telegram_module._validated_token_fingerprints.clear()

    def test_network_exception_log_never_contains_token(self) -> None:
        import requests

        settings = _settings_stub(TELEGRAM_TOKEN=_SYNTHETIC_TOKEN)
        url_with_token = f"https://api.telegram.org/bot{_SYNTHETIC_TOKEN}/getMe"
        exc = requests.exceptions.ConnectionError(f"Failed to establish a connection to {url_with_token}")

        with self.assertLogs("infrastructure.telegram", level="ERROR") as captured:
            with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
                 mock.patch("requests.get", side_effect=exc):
                telegram_module.telegram_ready()

        full_log = "\n".join(captured.output)
        self.assertNotIn(_SYNTHETIC_TOKEN, full_log)
        self.assertNotIn("synthetic-test-token", full_log)
        self.assertNotIn(url_with_token, full_log)

    def test_send_message_failure_log_never_contains_token(self) -> None:
        import requests

        settings = _settings_stub(TELEGRAM_TOKEN=_SYNTHETIC_TOKEN)
        url_with_token = f"https://api.telegram.org/bot{_SYNTHETIC_TOKEN}/sendMessage"
        exc = requests.exceptions.RequestException(f"error calling {url_with_token}")

        with self.assertLogs("infrastructure.telegram", level="ERROR") as captured:
            with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
                 mock.patch("requests.get", return_value=_get_me_response()), \
                 mock.patch("requests.post", side_effect=exc):
                telegram_module.send_message("chat-1", "x", retries=1, backoff_base=1.0)

        full_log = "\n".join(captured.output)
        self.assertNotIn(_SYNTHETIC_TOKEN, full_log)
        self.assertNotIn(url_with_token, full_log)

    def test_no_logger_call_interpolates_secret_value_variables(self) -> None:
        """
        Garantia estatica: nenhuma chamada de log interpola uma VARIAVEL que
        carregue o valor do secret/token (ex.: `logger.warning("...%s", token)`
        ou `..., configured_secret)`). Mencionar o NOME do campo em uma string
        literal (ex.: "TELEGRAM_WEBHOOK_SECRET nao configurado") e seguro e
        esperado -- e apenas texto descritivo, nao o valor. O invariante real
        (nenhum VALOR sintetico de secret aparece em log de verdade) e
        coberto pelos testes de assertLogs acima, que capturam saida real.
        """
        import inspect
        import re

        source = inspect.getsource(telegram_module)
        log_calls = re.findall(r"log(?:ger)?\.(?:error|warning|info|debug|exception)\(([^)]*)\)", source, re.DOTALL)
        risky_variable_names = ("token", "secret_token", "configured_secret", "resolved_token")
        for call_args in log_calls:
            # Ignora o primeiro argumento (a string de formato) -- olha so
            # para os argumentos de interpolacao passados depois da virgula.
            parts = [p.strip() for p in call_args.split(",")][1:]
            for part in parts:
                self.assertNotIn(part, risky_variable_names, msg=f"log interpola variavel arriscada: {call_args!r}")

    def test_getme_timeout_log_never_contains_token(self) -> None:
        import requests

        settings = _settings_stub(TELEGRAM_TOKEN=_SYNTHETIC_TOKEN)
        url_with_token = f"https://api.telegram.org/bot{_SYNTHETIC_TOKEN}/getMe"
        exc = requests.exceptions.Timeout(f"timed out calling {url_with_token}")

        with self.assertLogs("infrastructure.telegram", level="ERROR") as captured:
            with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
                 mock.patch("requests.get", side_effect=exc):
                telegram_module.telegram_ready()

        full_log = "\n".join(captured.output)
        self.assertNotIn(_SYNTHETIC_TOKEN, full_log)
        self.assertNotIn(url_with_token, full_log)

    def test_get_webhook_info_error_log_never_contains_token(self) -> None:
        import requests

        settings = _settings_stub(TELEGRAM_TOKEN=_SYNTHETIC_TOKEN)
        url_with_token = f"https://api.telegram.org/bot{_SYNTHETIC_TOKEN}/getWebhookInfo"
        exc = requests.exceptions.ConnectionError(f"boom at {url_with_token}")

        with self.assertLogs("infrastructure.telegram", level="ERROR") as captured:
            with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
                 mock.patch("requests.get", side_effect=[_get_me_response(), exc]):
                telegram_module.get_webhook_info()

        full_log = "\n".join(captured.output)
        self.assertNotIn(_SYNTHETIC_TOKEN, full_log)
        self.assertNotIn(url_with_token, full_log)

    def test_set_webhook_error_log_never_contains_token(self) -> None:
        import requests

        settings = _settings_stub(TELEGRAM_TOKEN=_SYNTHETIC_TOKEN, TELEGRAM_WEBHOOK_SECRET=_SYNTHETIC_SECRET)
        url_with_token = f"https://api.telegram.org/bot{_SYNTHETIC_TOKEN}/setWebhook"
        exc = requests.exceptions.ConnectionError(f"boom at {url_with_token}")

        with self.assertLogs("infrastructure.telegram", level="ERROR") as captured:
            with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
                 mock.patch("requests.get", return_value=_get_me_response()), \
                 mock.patch("requests.post", side_effect=exc):
                telegram_module.set_webhook("https://example.test/webhook")

        full_log = "\n".join(captured.output)
        self.assertNotIn(_SYNTHETIC_TOKEN, full_log)
        self.assertNotIn(_SYNTHETIC_SECRET, full_log)
        self.assertNotIn(url_with_token, full_log)

    def test_delete_webhook_error_log_never_contains_token(self) -> None:
        import requests

        settings = _settings_stub(TELEGRAM_TOKEN=_SYNTHETIC_TOKEN)
        url_with_token = f"https://api.telegram.org/bot{_SYNTHETIC_TOKEN}/deleteWebhook"
        exc = requests.exceptions.ConnectionError(f"boom at {url_with_token}")

        with self.assertLogs("infrastructure.telegram", level="ERROR") as captured:
            with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
                 mock.patch("requests.get", return_value=_get_me_response()), \
                 mock.patch("requests.post", side_effect=exc):
                telegram_module.delete_webhook()

        full_log = "\n".join(captured.output)
        self.assertNotIn(_SYNTHETIC_TOKEN, full_log)
        self.assertNotIn(url_with_token, full_log)

    def test_get_updates_error_log_never_contains_token(self) -> None:
        import requests

        settings = _settings_stub(TELEGRAM_TOKEN=_SYNTHETIC_TOKEN)
        url_with_token = f"https://api.telegram.org/bot{_SYNTHETIC_TOKEN}/getUpdates"
        exc = requests.exceptions.ConnectionError(f"boom at {url_with_token}")

        with self.assertLogs("infrastructure.telegram", level="ERROR") as captured:
            with mock.patch.object(telegram_module, "get_settings", return_value=settings), \
                 mock.patch("requests.get", side_effect=[_get_me_response(), exc]):
                telegram_module.get_updates(offset=1)

        full_log = "\n".join(captured.output)
        self.assertNotIn(_SYNTHETIC_TOKEN, full_log)
        self.assertNotIn(url_with_token, full_log)


if __name__ == "__main__":
    unittest.main()
