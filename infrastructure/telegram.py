# infrastructure/telegram.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
import contextlib
import hashlib
import socket
import threading
import time
import requests
import urllib3.util.connection as urllib3_connection
from .config import get_settings
from .logging import get_logger

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

# Fingerprints (SHA-256) de tokens ja validados com sucesso pelo identity
# guard neste processo. So sucesso e cacheado -- falha nunca entra aqui, de
# forma que a proxima operacao sempre tenta getMe novamente.
_validated_token_fingerprints: set[str] = set()
_TELEGRAM_IPV4_LOCK = threading.Lock()


class TelegramGuardError(Exception):
    """
    Sinaliza que uma operacao Telegram foi bloqueada pelo guardrail
    (TELEGRAM_MODE=disabled, configuracao ausente ou identidade do bot nao
    confirmada) -- distinto de uma falha real de rede/entrega ja dentro de
    uma operacao autorizada.
    """



@contextlib.contextmanager
def _prefer_ipv4_for_telegram_requests():
    """
    Prefer IPv4 only while requests/urllib3 resolves Telegram hosts.

    The VPS reaches api.telegram.org over IPv4 but can stall on IPv6. Keep the
    override narrow, process-safe, and always restore urllib3's default resolver
    choice before returning to the rest of the app.
    """
    with _TELEGRAM_IPV4_LOCK:
        original_allowed_gai_family = urllib3_connection.allowed_gai_family
        urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
        try:
            yield
        finally:
            urllib3_connection.allowed_gai_family = original_allowed_gai_family


def _telegram_readiness_get(method: str, token: str, timeout: int = 10) -> requests.Response:
    """GET Telegram readiness endpoints with IPv4 preference and existing timeouts."""
    url = _TELEGRAM_API.format(token=token, method=method)
    with _prefer_ipv4_for_telegram_requests():
        return requests.get(url, timeout=timeout)

def _fingerprint(token: str) -> str:
    """SHA-256 do token, usado apenas como chave de cache em memoria (nunca logado)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_bot_identity(token: str, expected_bot_id: int) -> None:
    """
    Identity guard: chama getMe (fora da fronteira _guard, para nao recursar)
    e confirma result.id == expected_bot_id e result.is_bot is True.

    Levanta TelegramGuardError em qualquer cenario de bloqueio. Sucesso e
    cacheado por fingerprint do token; falha NUNCA e cacheada, permitindo
    que uma operacao futura tente getMe novamente.
    """
    fp = _fingerprint(token)
    if fp in _validated_token_fingerprints:
        return

    try:
        resp = _telegram_readiness_get("getMe", token, timeout=10)
    except requests.RequestException as e:
        logger.error("Identity guard: falha de rede no getMe (%s).", type(e).__name__)
        raise TelegramGuardError("Falha de rede ao validar identidade do bot.") from e

    if resp.status_code != 200:
        logger.error("Identity guard: getMe retornou status HTTP %s.", resp.status_code)
        raise TelegramGuardError(f"getMe retornou status HTTP {resp.status_code}.")

    try:
        data = resp.json()
    except ValueError as e:
        logger.error("Identity guard: getMe retornou corpo que nao e JSON valido.")
        raise TelegramGuardError("Resposta getMe invalida (JSON malformado).") from e

    if not isinstance(data, dict) or not data.get("ok"):
        logger.error("Identity guard: getMe respondeu ok=false ou formato inesperado.")
        raise TelegramGuardError("getMe nao confirmou sucesso (ok=false).")

    result = data.get("result")
    if not isinstance(result, dict):
        logger.error("Identity guard: campo 'result' de getMe ausente ou invalido.")
        raise TelegramGuardError("Resposta getMe sem campo 'result' valido.")

    actual_id = result.get("id")
    is_bot = result.get("is_bot")

    # Bot IDs nao sao secrets -- podem aparecer em log/mensagem de erro.
    if actual_id != expected_bot_id:
        logger.error(
            "Identity guard: bot ID nao confere (esperado=%s, obtido=%s).",
            expected_bot_id, actual_id,
        )
        raise TelegramGuardError(
            f"Bot ID nao confere com TELEGRAM_EXPECTED_BOT_ID "
            f"(esperado={expected_bot_id}, obtido={actual_id})."
        )

    if is_bot is not True:
        logger.error("Identity guard: getMe.is_bot nao e True (bot ID=%s).", actual_id)
        raise TelegramGuardError("Identidade retornada nao e um bot valido (is_bot != true).")

    _validated_token_fingerprints.add(fp)


def _guard(token: Optional[str] = None) -> str:
    """
    Fronteira comum de todas as operacoes Telegram: valida TELEGRAM_MODE,
    resolve o token efetivo e executa o identity guard (lazy/cacheado) antes
    de qualquer chamada de rede real. Retorna o token validado para uso pelo
    chamador. Levanta TelegramGuardError se a operacao nao puder prosseguir.
    """
    settings = get_settings()
    mode = settings.TELEGRAM_MODE

    if mode == "disabled":
        raise TelegramGuardError("TELEGRAM_MODE=disabled -- nenhuma operacao Telegram e permitida.")

    resolved_token = token or settings.TELEGRAM_TOKEN
    if not resolved_token:
        raise TelegramGuardError("TELEGRAM_TOKEN nao configurado.")

    expected_bot_id = settings.TELEGRAM_EXPECTED_BOT_ID
    if not expected_bot_id:
        raise TelegramGuardError("TELEGRAM_EXPECTED_BOT_ID nao configurado.")

    _validate_bot_identity(resolved_token, expected_bot_id)
    return resolved_token


def telegram_ready(token: Optional[str] = None) -> bool:
    """
    Verifica se e seguro realizar operacoes Telegram agora (TELEGRAM_MODE
    ativo + identidade do bot confirmada). Nao levanta excecao -- retorna
    False para qualquer bloqueio. Chamado explicitamente por workers/notifier.py
    e app/routes/webhook_telegram.py antes de qualquer side effect.
    """
    try:
        _guard(token)
        return True
    except TelegramGuardError:
        return False


def _post(method: str, payload: Dict[str, Any], token: str, timeout: int = 15) -> requests.Response:
    """Chamada HTTP crua (POST), sem guard -- usada internamente apos _guard() ja ter validado."""
    url = _TELEGRAM_API.format(token=token, method=method)
    return requests.post(url, json=payload, timeout=timeout)


def send_message(
    chat_id: str | int,
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    retries: int = 3,
    backoff_base: float = 1.5,
    token: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Envia mensagem ao Telegram com retries exponenciais.
    Aceita reply_markup p/ inline keyboard.
    """
    try:
        resolved_token = _guard(token)
    except TelegramGuardError as e:
        logger.warning("send_message bloqueado pelo guardrail: %s", e)
        return False

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    for attempt in range(1, retries + 1):
        try:
            resp = _post("sendMessage", payload, resolved_token)
            if resp.status_code == 200:
                return True
            logger.error("Telegram falhou (%s).", resp.status_code)
        except requests.RequestException as e:
            # A representacao textual de RequestException pode conter a URL
            # da requisicao (com o token) -- nunca logar "e" diretamente.
            logger.error("Erro ao enviar Telegram (tentativa %s): %s", attempt, type(e).__name__)

        time.sleep(backoff_base ** attempt)

    return False


def get_webhook_info(token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        resolved_token = _guard(token)
    except TelegramGuardError as e:
        logger.warning("get_webhook_info bloqueado pelo guardrail: %s", e)
        return None
    try:
        r = _telegram_readiness_get("getWebhookInfo", resolved_token, timeout=10)
        data = r.json()
        return data if isinstance(data, dict) else None
    except requests.RequestException as e:
        logger.error("getWebhookInfo falhou: %s", type(e).__name__)
        return None


def set_webhook(
    webhook_url: str,
    *,
    token: Optional[str] = None,
    drop_pending: bool = False,
    secret_token: Optional[str] = None,
) -> bool:
    """
    Registra o webhook. O secret enviado ao Telegram e SEMPRE
    settings.TELEGRAM_WEBHOOK_SECRET -- nunca depende de um chamador externo
    lembrar de passar o valor certo. Se nao houver secret configurado, a
    operacao e bloqueada (nunca registra webhook sem secret). Se
    secret_token for informado explicitamente e divergir do configurado,
    tambem bloqueia antes de qualquer requisicao (evita registrar um
    webhook com secret diferente do que o proprio endpoint valida).
    """
    try:
        resolved_token = _guard(token)
    except TelegramGuardError as e:
        logger.warning("set_webhook bloqueado pelo guardrail: %s", e)
        return False

    configured_secret = get_settings().TELEGRAM_WEBHOOK_SECRET
    if not configured_secret:
        logger.warning(
            "set_webhook bloqueado: TELEGRAM_WEBHOOK_SECRET nao configurado -- "
            "nunca registrar webhook sem secret."
        )
        return False
    if secret_token is not None and secret_token != configured_secret:
        logger.warning("set_webhook bloqueado: secret_token informado diverge do configurado.")
        return False

    try:
        url = _TELEGRAM_API.format(token=resolved_token, method="setWebhook")
        data: Dict[str, Any] = {
            "url": webhook_url,
            "drop_pending_updates": str(drop_pending).lower(),
            "secret_token": configured_secret,
        }
        r = requests.post(url, data=data, timeout=15)
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            logger.error("setWebhook falhou: status=%s.", r.status_code)
        return bool(ok)
    except requests.RequestException as e:
        logger.error("setWebhook erro: %s", type(e).__name__)
        return False


def delete_webhook(*, token: Optional[str] = None, drop_pending: bool = True) -> bool:
    try:
        resolved_token = _guard(token)
    except TelegramGuardError as e:
        logger.warning("delete_webhook bloqueado pelo guardrail: %s", e)
        return False
    try:
        url = _TELEGRAM_API.format(token=resolved_token, method="deleteWebhook")
        r = requests.post(url, data={"drop_pending_updates": str(drop_pending).lower()}, timeout=15)
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            logger.error("deleteWebhook falhou: status=%s.", r.status_code)
        return bool(ok)
    except requests.RequestException as e:
        logger.error("deleteWebhook erro: %s", type(e).__name__)
        return False


def get_updates(
    *,
    offset: Optional[int] = None,
    timeout: int = 30,
    allowed_updates: Optional[List[str]] = None,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    getUpdates (long-polling). Usado apenas por scripts/telegram_poll.py
    (desenvolvimento local) -- producao/homologacao usam webhook.
    """
    try:
        resolved_token = _guard(token)
    except TelegramGuardError as e:
        logger.warning("get_updates bloqueado pelo guardrail: %s", e)
        return None
    try:
        url = _TELEGRAM_API.format(token=resolved_token, method="getUpdates")
        params: Dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        if allowed_updates is not None:
            params["allowed_updates"] = allowed_updates
        r = requests.get(url, params=params, timeout=timeout + 10)
        data = r.json()
        return data if isinstance(data, dict) else None
    except requests.RequestException as e:
        logger.error("getUpdates falhou: %s", type(e).__name__)
        return None
