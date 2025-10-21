
# workers/notifier.py
from __future__ import annotations

import html as py_html
from typing import Dict, Optional

from infrastructure.logging import get_logger
from infrastructure.db import SessionLocal
from infrastructure.telegram import send_message
from domain.repositories import (
    get_unnotified_user_projects,
    mark_project_notified,
    increment_notify_attempts,
)

# >>> importa do módulo certo (alinhado com infrastructure/scraping.py)
try:
    from infrastructure.scraping import fetch_html, scrape_99freelas_detail  # type: ignore
except Exception:  # pragma: no cover
    fetch_html = None
    scrape_99freelas_detail = None

logger = get_logger(__name__)
MAX_ATTEMPTS = 5


# ===================== helpers =====================

def esc(s: Optional[str]) -> str:
    """Escape seguro para HTML do Telegram."""
    return py_html.escape((s or "").strip())

def priority_label(age_min: Optional[int], proposals: Optional[int]) -> Optional[str]:
    """
    Regra simples de prioridade:
      🔥 Alta  => publicado <= 60 min  e propostas <= 2
      🟡 Média => publicado <= 6 h    e propostas <= 5
      ⚪ Baixa => demais casos
    """
    if age_min is None and proposals is None:
        return None

    age = age_min if age_min is not None else 999999
    prop = proposals if proposals is not None else 999

    if age <= 60 and prop <= 2:
        return "🔥 Alta prioridade"
    if age <= 6 * 60 and prop <= 5:
        return "🟡 Prioridade média"
    return "⚪ Prioridade baixa"

def human_age_from_minutes(age_min: Optional[int]) -> Optional[str]:
    if age_min is None:
        return None
    if age_min < 60:
        return f"{age_min} min"
    if age_min < 24 * 60:
        return f"{age_min // 60} h"
    return f"{age_min // (60 * 24)} d"

def _button_open(link: str) -> dict:
    """InlineKeyboardMarkup simples com 1 botão."""
    label = "🌐 Abrir no 99Freelas" if "99freelas" in (link or "").lower() else "🌐 Abrir"
    return {"inline_keyboard": [[{"text": label, "url": link}]]}


# ===================== renderização do card =====================

def _render_rich_message(
    *,
    title: str,
    link: str,
    matched_kw: str,
    extra: Dict[str, object] | None,
) -> str:
    """
    Card enriquecido com:
      - prioridade
      - status (categoria, nível, publicado, propostas, interessados)
      - cliente (nome, rating, #reviews)
    """
    extra = extra or {}
    cat = extra.get("category") or None
    level = extra.get("level") or None
    age_min = extra.get("age_minutes") if isinstance(extra.get("age_minutes"), int) else None
    proposals = extra.get("proposals") if isinstance(extra.get("proposals"), int) else None
    interested = extra.get("interested") if isinstance(extra.get("interested"), int) else None
    client_name = extra.get("client_name") or None
    client_rating = extra.get("client_rating") if isinstance(extra.get("client_rating"), (int, float)) else None
    client_reviews = extra.get("client_reviews") if isinstance(extra.get("client_reviews"), int) else None

    prio = priority_label(age_min, proposals)
    prio_line = f"  <b>{prio}</b>" if prio else ""

    parts: list[str] = []
    parts.append(f"🆕 <b>Projeto encontrado</b>{prio_line}\n")
    parts.append(f"🎯 <b>Match:</b> <code>{esc(matched_kw)}</code>")
    parts.append(f"🧾 <b>Título:</b> {esc(title)}\n")

    status_lines: list[str] = []
    meta1: list[str] = []
    if cat:
        meta1.append(f"Categoria: <b>{esc(str(cat))}</b>")
    if level:
        meta1.append(f"Nível: <b>{esc(str(level))}</b>")
    if meta1:
        status_lines.append("• " + " • ".join(meta1))

    meta2: list[str] = []
    age_h = human_age_from_minutes(age_min)
    if age_h:
        meta2.append(f"Publicado: <b>{age_h}</b>")
    if proposals is not None:
        meta2.append(f"Propostas: <b>{proposals}</b>")
    if interested is not None:
        meta2.append(f"Interessados: <b>{interested}</b>")
    if meta2:
        status_lines.append("• " + " • ".join(meta2))

    if status_lines:
        parts.append("<b>📊 Status</b>")
        parts.extend(status_lines)
        parts.append("")  # linha em branco

    client_bits: list[str] = []
    if client_name:
        client_bits.append(esc(str(client_name)))
    if client_rating is not None:
        star = f"⭐ <b>{float(client_rating):.1f}</b>"
        if client_reviews:
            star += f" ({client_reviews} avaliações)"
        client_bits.append(star)
    if client_bits:
        parts.append("<b>👤 Cliente</b>")
        parts.append("• " + " — ".join(client_bits))
        parts.append("")

    parts.append("👉 Toque no botão abaixo para abrir:")
    return "\n".join(parts).strip()

def _render_basic_message(title: str, matched_kw: str) -> str:
    """Fallback simples (usado se não conseguirmos extrair extras)."""
    return (
        "🆕 <b>Projeto encontrado</b>\n\n"
        f"🎯 <b>Match:</b> <code>{esc(matched_kw)}</code>\n"
        f"🧾 <b>Título:</b> {esc(title)}\n\n"
        "👉 Toque no botão abaixo para abrir:"
    )


# ===================== fluxo principal =====================

def _build_message_for_project(ppu) -> str:
    """Decide se enriquece (99Freelas) e monta o card."""
    title = ppu.title or "Projeto"
    link = ppu.link or ""
    matched_kw = ppu.matched_keyword or ""

    # Enriquecimento apenas para 99Freelas
    is_99 = "99freelas.com" in (link or "").lower()
    if is_99 and fetch_html and scrape_99freelas_detail:
        try:
            html = fetch_html(link)  # type: ignore[misc]
            if html:
                extra = scrape_99freelas_detail(html)  # type: ignore[misc]
                return _render_rich_message(title=title, link=link, matched_kw=matched_kw, extra=extra)
        except Exception as e:  # robusto: falhou o enrichment, segue o básico
            logger.warning("[notifier] enrich falhou para link=%s: %s", link, e)

    # fallback básico
    return _render_basic_message(title, matched_kw)

def notify_pending(max_batch: int = 100) -> int:
    """
    Envia mensagens pendentes aos usuários.
    Retorna quantidade enviada com sucesso.
    """
    sent = 0
    with SessionLocal() as db:
        pendings = get_unnotified_user_projects(db, limit=max_batch)
        if not pendings:
            logger.info("[notifier] Sem pendências.")
            return 0

        for ppu in pendings:
            chat_id = ppu.user.chat_id if ppu.user else None
            if not chat_id:
                logger.warning("[notifier] user_id=%s sem chat_id - ignorando.", ppu.user_id)
                increment_notify_attempts(db, ppu)
                continue

            text = _build_message_for_project(ppu)
            ok = send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,  # mantém o visual enxuto
                reply_markup=_button_open(ppu.link),
            )

            if ok:
                mark_project_notified(db, ppu)
                sent += 1
            else:
                increment_notify_attempts(db, ppu)
                if ppu.notify_attempts >= MAX_ATTEMPTS:
                    logger.error(
                        "[notifier] Desistindo de user_project id=%s após %s tentativas.",
                        ppu.id, ppu.notify_attempts
                    )

    logger.info("[notifier] enviadas=%s", sent)
    return sent
