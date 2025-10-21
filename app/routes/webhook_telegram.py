# app/routes/webhook_telegram.py
from __future__ import annotations

from flask import Blueprint, request, jsonify

from app import csrf
from infrastructure.logging import get_logger
from infrastructure.db import SessionLocal
from infrastructure.telegram import send_message
from domain.repositories import get_user_by_telegram_code, save_chat_binding

bp = Blueprint("webhook", __name__)
log = get_logger(__name__)

@bp.post("/telegram")
@csrf.exempt  # Telegram não envia CSRF; precisamos isentar
def telegram_webhook():
    """
    Fluxo esperado:
      - Usuário envia no Telegram: /start <codigo>
      - Recebemos update JSON aqui; vinculamos chat_id ao user do código e invalidamos o código.
    """
    data = request.get_json(silent=True) or {}
    message = data.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    # Sem mensagem ou sem chat_id: apenas ack
    if not text or not chat_id:
        return jsonify({"status": "ignored"}), 200

    if text.startswith("/start"):
        parts = text.split()
        if len(parts) != 2:
            send_message(chat_id, "Envie: /start <código> para vincular sua conta.")
            return jsonify({"status": "missing_code"}), 200

        code = parts[1]
        with SessionLocal() as db:
            user = get_user_by_telegram_code(db, code)
            if not user:
                send_message(chat_id, "❌ Código inválido ou expirado.")
                return jsonify({"status": "invalid_code"}), 200

            save_chat_binding(db, user, str(chat_id))
            send_message(chat_id, "✅ Seu Telegram foi vinculado com sucesso!")
            log.info("Vínculo Telegram ok: user_id=%s chat_id=%s", user.id, chat_id)
            return jsonify({"status": "linked"}), 200

    # Outros comandos: ignore com ack
    return jsonify({"status": "ok"}), 200
