"""
Polling local para desenvolvimento — substitui o webhook do Telegram.

Em produção o Telegram entrega updates via POST ao endpoint /webhook/telegram.
Em dev, esse endpoint não é acessível externamente (localhost), então este
script usa getUpdates para buscar updates e processar com a mesma lógica.

Uso:
    .venv\\Scripts\\python.exe scripts\\telegram_poll.py

Interrompa com Ctrl+C.
"""
from __future__ import annotations

import time
import sys
import os

# Garante que o root do projeto está no path antes de qualquer import local
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from sqlalchemy import select

from config import settings
from infrastructure.db import SessionLocal
from infrastructure.logging import get_logger
from infrastructure.telegram import send_message
from domain.models import User
from domain.repositories import get_user_by_telegram_code, save_chat_binding

log = get_logger("telegram_poll")

POLL_INTERVAL = 2  # segundos entre chamadas a getUpdates
TIMEOUT_SEC = 30   # long-poll timeout para a API do Telegram


def _send(chat_id: int | str, text: str) -> None:
    try:
        send_message(chat_id, text)
    except Exception:
        log.exception("Falha ao enviar mensagem para chat_id=%s", chat_id)


def _process_message(message: dict) -> None:
    text: str = (message.get("text") or "").strip()
    chat_id: int | None = (message.get("chat") or {}).get("id")

    if not text or not chat_id:
        return

    if not text.startswith("/start"):
        return

    parts = text.split(maxsplit=1)
    code = parts[1].strip() if len(parts) == 2 else ""

    if not code:
        _send(
            chat_id,
            "👋 Olá! Para vincular sua conta SmartPayBot, abra o dashboard, "
            "copie o código de vinculação e envie:\n\n"
            "/start SEU_CÓDIGO\n\n"
            "Se ainda não tem uma conta, acesse o SmartPayBot e cadastre-se.",
        )
        return

    with SessionLocal() as db:
        already_owner = db.scalar(
            select(User).where(User.chat_id == str(chat_id))
        )
        if already_owner:
            _send(
                chat_id,
                "⚠️ Este chat já está vinculado à conta *{}*.\n"
                "Se quiser vincular a outra conta, desvincule primeiro no dashboard.".format(
                    already_owner.username
                ),
            )
            return

        user = get_user_by_telegram_code(db, code)
        if not user:
            _send(
                chat_id,
                "❌ Código inválido ou expirado.\n"
                "Acesse o dashboard e gere um novo código de vinculação.",
            )
            return

        save_chat_binding(db, user, str(chat_id))
        _send(
            chat_id,
            "✅ Tudo certo! Sua conta *{}* foi vinculada com sucesso.\n"
            "A partir de agora você receberá alertas de novos projetos aqui. 🚀".format(
                user.username
            ),
        )
        log.info("Vínculo Telegram ok via polling: user_id=%s chat_id=%s", user.id, chat_id)


def run_polling() -> None:
    token = settings.TELEGRAM_TOKEN
    if not token:
        log.error("TELEGRAM_TOKEN não configurado no .env. Abortando.")
        sys.exit(1)

    base_url = f"https://api.telegram.org/bot{token}"
    offset: int | None = None

    log.info("Polling Telegram iniciado (Ctrl+C para parar)...")

    with httpx.Client(timeout=TIMEOUT_SEC + 5) as client:
        while True:
            try:
                params: dict = {"timeout": TIMEOUT_SEC, "allowed_updates": ["message"]}
                if offset is not None:
                    params["offset"] = offset

                resp = client.get(f"{base_url}/getUpdates", params=params)
                resp.raise_for_status()
                data = resp.json()

                if not data.get("ok"):
                    log.warning("getUpdates retornou ok=false: %s", data)
                    time.sleep(POLL_INTERVAL)
                    continue

                updates: list[dict] = data.get("result") or []
                for update in updates:
                    update_id: int = update["update_id"]
                    offset = update_id + 1  # marca como processado

                    message = update.get("message")
                    if message:
                        try:
                            _process_message(message)
                        except Exception:
                            log.exception("Erro ao processar update_id=%s", update_id)

                if not updates:
                    time.sleep(POLL_INTERVAL)

            except httpx.TimeoutException:
                # Long-poll expirou sem updates — normal
                continue
            except KeyboardInterrupt:
                log.info("Polling encerrado pelo usuário.")
                break
            except Exception:
                log.exception("Erro no loop de polling. Aguardando %ds...", POLL_INTERVAL * 5)
                time.sleep(POLL_INTERVAL * 5)


if __name__ == "__main__":
    run_polling()
