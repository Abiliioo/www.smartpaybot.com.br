# infrastructure/telegram.py
from __future__ import annotations
from typing import Optional, Dict, Any
import time
import requests
from .config import get_settings
from .logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

def _post(method: str, payload: Dict[str, Any], token: Optional[str] = None, timeout: int = 15) -> requests.Response:
    token = token or settings.TELEGRAM_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN não configurado.")
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
    reply_markup: Optional[Dict[str, Any]] = None,  # <— NOVO
) -> bool:
    """
    Envia mensagem ao Telegram com retries exponenciais.
    Aceita reply_markup p/ inline keyboard.
    """
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup  # <— NOVO

    for attempt in range(1, retries + 1):
        try:
            resp = _post("sendMessage", payload, token=token)
            if resp.status_code == 200:
                return True
            logger.error("Telegram falhou (%s): %s", resp.status_code, resp.text)
        except requests.RequestException as e:
            logger.error("Erro ao enviar Telegram (tentativa %s): %s", attempt, e)

        time.sleep(backoff_base ** attempt)

    return False



def get_webhook_info(token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    token = token or settings.TELEGRAM_TOKEN
    if not token:
        return None
    try:
        url = _TELEGRAM_API.format(token=token, method="getWebhookInfo")
        r = requests.get(url, timeout=10)
        data = r.json()
        return data if isinstance(data, dict) else None
    except requests.RequestException as e:
        logger.error("getWebhookInfo falhou: %s", e)
        return None

def set_webhook(
    webhook_url: str,
    *,
    token: Optional[str] = None,
    drop_pending: bool = False,
    secret_token: Optional[str] = None,
) -> bool:
    token = token or settings.TELEGRAM_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN não configurado.")
    try:
        url = _TELEGRAM_API.format(token=token, method="setWebhook")
        data: Dict[str, Any] = {
            "url": webhook_url,
            "drop_pending_updates": str(drop_pending).lower(),
        }
        if secret_token:
            data["secret_token"] = secret_token
        r = requests.post(url, data=data, timeout=15)
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            logger.error("setWebhook falhou: %s", r.text)
        return bool(ok)
    except requests.RequestException as e:
        logger.error("setWebhook erro: %s", e)
        return False

def delete_webhook(*, token: Optional[str] = None, drop_pending: bool = True) -> bool:
    token = token or settings.TELEGRAM_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN não configurado.")
    try:
        url = _TELEGRAM_API.format(token=token, method="deleteWebhook")
        r = requests.post(url, data={"drop_pending_updates": str(drop_pending).lower()}, timeout=15)
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            logger.error("deleteWebhook falhou: %s", r.text)
        return bool(ok)
    except requests.RequestException as e:
        logger.error("deleteWebhook erro: %s", e)
        return False
