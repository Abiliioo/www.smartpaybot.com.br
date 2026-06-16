"""
Polling local para desenvolvimento — substitui o webhook do Telegram.

Em produção o Telegram entrega updates via POST ao endpoint /webhook/telegram.
Em dev, esse endpoint não é acessível externamente (localhost), então este
script usa getUpdates para buscar updates e processar com a mesma lógica.

Uso (a partir da raiz do projeto):
    .venv\\Scripts\\python.exe scripts\\telegram_poll.py

Interrompa com Ctrl+C.
"""
from __future__ import annotations

import os
import sys
import time

# Garante que a raiz do projeto está no sys.path quando o script é executado
# diretamente com: .venv\Scripts\python.exe scripts\telegram_poll.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import select

from infrastructure.config import get_settings
from infrastructure.db import SessionLocal
from infrastructure.logging import configure_logging, get_logger
from infrastructure.telegram import send_message
from domain.models import User
from domain.repositories import get_user_by_telegram_code, save_chat_binding

log = get_logger("telegram_poll")

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

POLL_TIMEOUT = 30   # long-poll: segundos que a API do Telegram aguarda antes de retornar vazio
RETRY_SLEEP = 5     # segundos de espera após erro de rede


def _masked_token(token: str) -> str:
    """Exibe só os primeiros 8 caracteres do token para debug seguro."""
    return token[:8] + "..." if len(token) > 8 else "***"


def _send(chat_id: int | str, text: str) -> None:
    try:
        send_message(chat_id, text)
    except Exception:
        log.exception("Falha ao enviar mensagem para chat_id=%s", chat_id)


def _process_message(message: dict) -> None:
    text: str = (message.get("text") or "").strip()
    chat_id: int | None = (message.get("chat") or {}).get("id")
    from_user: str = ((message.get("from") or {}).get("username") or "desconhecido")

    if not text or not chat_id:
        log.debug("Mensagem sem texto ou chat_id — ignorada")
        return

    if not text.startswith("/start"):
        log.debug("chat_id=%s enviou %r — ignorado (não é /start)", chat_id, text[:30])
        return

    log.info("Processando /start de chat_id=%s (@%s)", chat_id, from_user)

    parts = text.split(maxsplit=1)
    code = parts[1].strip() if len(parts) == 2 else ""

    if not code:
        log.warning("chat_id=%s enviou /start sem código", chat_id)
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
            log.warning(
                "chat_id=%s já vinculado ao user_id=%s (%s)",
                chat_id, already_owner.id, already_owner.username,
            )
            _send(
                chat_id,
                "⚠️ Este chat já está vinculado à conta <b>{}</b>.\n"
                "Se quiser vincular a outra conta, desvincule primeiro no dashboard.".format(
                    already_owner.username
                ),
            )
            return

        user = get_user_by_telegram_code(db, code)
        if not user:
            log.warning("chat_id=%s usou código inválido/expirado: %r", chat_id, code)
            _send(
                chat_id,
                "❌ Código inválido ou expirado.\n"
                "Acesse o dashboard e gere um novo código de vinculação.",
            )
            return

        save_chat_binding(db, user, str(chat_id))
        log.info(
            "Vínculo Telegram ok: user_id=%s username=%s chat_id=%s",
            user.id, user.username, chat_id,
        )
        _send(
            chat_id,
            "✅ Tudo certo! Sua conta <b>{}</b> foi vinculada com sucesso.\n"
            "A partir de agora você receberá alertas de novos projetos aqui. 🚀".format(
                user.username
            ),
        )


def run_polling() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    token = settings.TELEGRAM_TOKEN
    if not token:
        print("ERRO: TELEGRAM_TOKEN não configurado no .env. Abortando.", flush=True)
        sys.exit(1)

    bot_name = f"@{settings.TELEGRAM_BOT_USERNAME}" if settings.TELEGRAM_BOT_USERNAME else "(bot_username não definido)"

    print("", flush=True)
    print("=" * 50, flush=True)
    print("  SmartPayBot — Telegram Polling (dev)", flush=True)
    print(f"  Bot     : {bot_name}", flush=True)
    print(f"  Token   : {_masked_token(token)}", flush=True)
    print(f"  Timeout : {POLL_TIMEOUT}s por ciclo", flush=True)
    print("=" * 50, flush=True)
    print("  Abra o bot no Telegram e envie:", flush=True)
    print("  /start <codigo>", flush=True)
    print("  (o código aparece no dashboard > card Telegram)", flush=True)
    print("=" * 50, flush=True)
    print("  Ctrl+C para parar", flush=True)
    print("", flush=True)

    base_url = _TELEGRAM_API.format(token=token, method="{method}")
    offset: int | None = None

    session = requests.Session()
    try:
        while True:
            params: dict = {
                "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message"],
            }
            if offset is not None:
                params["offset"] = offset

            log.debug("getUpdates (offset=%s, timeout=%ds)...", offset, POLL_TIMEOUT)

            try:
                resp = session.get(
                    base_url.format(method="getUpdates"),
                    params=params,
                    timeout=POLL_TIMEOUT + 10,  # margem acima do long-poll
                )
                resp.raise_for_status()
                data = resp.json()

                if not data.get("ok"):
                    log.warning("getUpdates retornou ok=false: %s", data)
                    time.sleep(RETRY_SLEEP)
                    continue

                updates: list[dict] = data.get("result") or []

                if updates:
                    log.info("Recebidos %d update(s)", len(updates))

                for update in updates:
                    update_id: int = update["update_id"]
                    offset = update_id + 1

                    message = update.get("message")
                    if not message:
                        log.debug("update_id=%s sem campo 'message' — ignorado", update_id)
                        continue

                    try:
                        _process_message(message)
                    except Exception:
                        log.exception("Erro ao processar update_id=%s", update_id)

            except requests.Timeout:
                # Long-poll expirou sem updates — comportamento normal
                log.debug("Long-poll expirou sem updates — aguardando próximo ciclo")
                continue
            except requests.RequestException as e:
                log.error("Erro de rede: %s. Aguardando %ds...", e, RETRY_SLEEP)
                time.sleep(RETRY_SLEEP)

    except KeyboardInterrupt:
        print("\nPolling encerrado.", flush=True)
        log.info("Polling encerrado pelo usuário.")
    finally:
        session.close()


if __name__ == "__main__":
    run_polling()
