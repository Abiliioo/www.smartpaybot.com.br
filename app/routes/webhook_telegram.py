# app/routes/webhook_telegram.py
from __future__ import annotations

from flask import Blueprint, request, jsonify
from sqlalchemy import select

from app import csrf
from infrastructure.config import get_settings
from infrastructure.logging import get_logger
from infrastructure.db import SessionLocal
from infrastructure.telegram import send_message
from domain.models import User
from domain.repositories import get_user_by_telegram_code, save_chat_binding

bp = Blueprint("webhook", __name__)
log = get_logger(__name__)

# Evita logar o aviso de "sem secret" em toda requisição
_no_secret_warned = False


def _send(chat_id: int | str, text: str) -> None:
    try:
        send_message(chat_id, text)
    except Exception:
        log.exception("Falha ao enviar mensagem Telegram para chat_id=%s", chat_id)


def _check_secret() -> bool:
    """
    Valida X-Telegram-Bot-Api-Secret-Token quando TELEGRAM_WEBHOOK_SECRET está configurado.
    Retorna True se a requisição pode prosseguir, False se deve ser rejeitada.
    """
    global _no_secret_warned
    expected = get_settings().TELEGRAM_WEBHOOK_SECRET
    if expected:
        incoming = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if incoming != expected:
            log.warning("Webhook Telegram rejeitado: secret inválido ou ausente")
            return False
        return True
    # Sem secret configurado: permitir, mas avisar uma vez
    if not _no_secret_warned:
        log.warning(
            "TELEGRAM_WEBHOOK_SECRET não configurado — webhook aceita requisições sem autenticação. "
            "Configure em produção via .env."
        )
        _no_secret_warned = True
    return True


@bp.post("/telegram")
@csrf.exempt  # Telegram não envia CSRF; precisamos isentar
def telegram_webhook():
    if not _check_secret():
        return jsonify({"status": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    message = data.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    if not text or not chat_id:
        return jsonify({"status": "ignored"}), 200

    if text.startswith("/start"):
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
            return jsonify({"status": "missing_code"}), 200

        with SessionLocal() as db:
            # Verificar se este chat já está vinculado a outro usuário
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
                return jsonify({"status": "already_linked"}), 200

            user = get_user_by_telegram_code(db, code)
            if not user:
                _send(
                    chat_id,
                    "❌ Código inválido ou expirado.\n"
                    "Acesse o dashboard e gere um novo código de vinculação.",
                )
                return jsonify({"status": "invalid_code"}), 200

            save_chat_binding(db, user, str(chat_id))
            _send(
                chat_id,
                "✅ Tudo certo! Sua conta *{}* foi vinculada com sucesso.\n"
                "A partir de agora você receberá alertas de novos projetos aqui. 🚀".format(
                    user.username
                ),
            )
            log.info("Vínculo Telegram ok: user_id=%s chat_id=%s", user.id, chat_id)
            return jsonify({"status": "linked"}), 200

    return jsonify({"status": "ok"}), 200
