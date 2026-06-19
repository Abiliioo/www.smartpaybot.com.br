# workers/notifier.py
from __future__ import annotations

import html as py_html
import re
from datetime import datetime, timezone
from typing import Dict, Optional

from infrastructure.logging import get_logger
from infrastructure.db import SessionLocal
from infrastructure.telegram import send_message
from domain.repositories import (
    get_unnotified_user_projects,
    mark_project_notified,
    increment_notify_attempts,
)
from domain.services.plan_service import can_receive_alert_today, increment_alert_count

# Enriquecimento (detalhe + fallback listagem)
try:
    from infrastructure.scraping import (
        fetch_html,
        scrape_99freelas_detail,
        enrich_from_list_pages,
    )  # type: ignore
except Exception:  # pragma: no cover
    fetch_html = None
    scrape_99freelas_detail = None
    enrich_from_list_pages = None

logger = get_logger(__name__)
MAX_ATTEMPTS = 5


# ===================== helpers =====================

def esc(s: Optional[str]) -> str:
    return py_html.escape((s or "").strip())

def _plural(n: int, sing: str, plur: str) -> str:
    return sing if n == 1 else plur

def human_ago_from_minutes(age_min: Optional[int]) -> Optional[str]:
    if age_min is None:
        return None
    if age_min < 60:
        return f"há {age_min} {_plural(age_min, 'minuto', 'minutos')}"
    if age_min < 24 * 60:
        h = age_min // 60
        return f"há {h} {_plural(h, 'hora', 'horas')}"
    d = age_min // (60 * 24)
    return f"há {d} {_plural(d, 'dia', 'dias')}"

def priority_label_by_proposals(proposals: Optional[int]) -> Optional[str]:
    """
    Priorização 100% baseada em propostas (sem usar idade):
      - 0            => 🚀 Zero propostas até agora — Seja o primeiro a enviar!
      - 1..2         => 🟡 Alta chance — Poucos ainda aplicaram
      - 3..5         => ⚪ Moderada — Alguns freelancers aplicaram
      - >5           => ⚫ Baixa — Vaga disputada
    """
    if proposals is None:
        return None
    if proposals == 0:
        return "🚀 Zero propostas até agora — seja o primeiro a enviar!"
    if proposals <= 2:
        return "🟡 Pouca concorrência — ainda dá para se destacar"
    if proposals <= 5:
        return "⚪ Moderada — algumas propostas já enviadas"
    return "⚫ Baixa — vaga disputada"

def _button_open(link: str) -> dict:
    label = "🌐 Abrir no 99Freelas" if "99freelas" in (link or "").lower() else "🌐 Abrir"
    return {"inline_keyboard": [[{"text": label, "url": link}]]}

def _project_id_from_link(link: str) -> Optional[int]:
    if not link:
        return None
    m = re.search(r"(\d+)(?:\D*$|$)", link)
    try:
        return int(m.group(1)) if m else None
    except Exception:
        return None

def _first_non_empty(*vals):
    for v in vals:
        if v not in (None, "", {}):
            return v
    return None

def _merge_enrich(detail: Dict[str, object] | None, listed: Dict[str, object] | None) -> Dict[str, object] | None:
    """Mescla campos, preferindo 'detail' e completando com 'listed'."""
    d = detail or {}
    l = listed or {}
    if not d and not l:
        return None

    keys = (
        "category", "level",
        "age_minutes",
        "proposals", "interested",
        "client_name", "client_rating", "client_reviews",
    )
    out: Dict[str, object] = {}
    for k in keys:
        out[k] = _first_non_empty(d.get(k), l.get(k))
    return out


# ===================== renderização =====================

def _render_status_block(
    *, age_min: Optional[int], proposals: Optional[int], interested: Optional[int],
    category: Optional[str], level: Optional[str]
) -> list[str]:
    lines: list[str] = []
    lines.append("<b>📊 Status</b>")

    if category:
        lines.append(f"Categoria: <b>{esc(category)}</b>")
    if level:
        lines.append(f"Nível: <b>{esc(level)}</b>")

    ago = human_ago_from_minutes(age_min)
    if ago:
        lines.append(f"Publicado: <b>{esc(ago)}</b>")
    if proposals is not None:
        lines.append(f"Propostas: <b>{proposals}</b>")
    if interested is not None:
        lines.append(f"Interessados: <b>{interested}</b>")
    return lines

def _render_rating_block(*, rating: Optional[float], reviews: Optional[int]) -> list[str]:
    if rating is None and reviews in (None, 0):
        return []
    row = []
    if rating is not None:
        row.append(f"⭐ <b>{float(rating):.1f}</b>")
    if isinstance(reviews, int) and reviews >= 0:
        if reviews == 0:
            row.append("(Sem feedback)")
        elif reviews == 1:
            row.append("(1 avaliação)")
        else:
            row.append(f"({reviews} avaliações)")
    return ["<b>⭐ Reputação do cliente</b>", " ".join(row).strip()]

def _render_rich_message(
    *, title: str, link: str, matched_kw: str, extra: Dict[str, object] | None,
) -> str:
    extra = extra or {}

    age_min = extra.get("age_minutes") if isinstance(extra.get("age_minutes"), int) else None
    proposals = extra.get("proposals") if isinstance(extra.get("proposals"), int) else None
    interested = extra.get("interested") if isinstance(extra.get("interested"), int) else None
    category = (extra.get("category") or None) and str(extra.get("category"))
    level = (extra.get("level") or None) and str(extra.get("level"))
    client_rating = extra.get("client_rating") if isinstance(extra.get("client_rating"), (int, float)) else None
    client_reviews = extra.get("client_reviews") if isinstance(extra.get("client_reviews"), int) else None

    prio = priority_label_by_proposals(proposals)

    parts: list[str] = []
    header = "💼 <b>Novo projeto disponível!</b>"
    if prio:
        header += f"\n{prio}"
    parts.append(header + "\n")

    parts.append(f"🎯 <b>Match:</b> <code>{esc(matched_kw)}</code>")
    parts.append(f"🧾 <b>Título:</b> {esc(title)}\n")

    status_lines = _render_status_block(
        age_min=age_min, proposals=proposals, interested=interested, category=category, level=level
    )
    if len(status_lines) > 1:
        parts.extend(status_lines)
        parts.append("")

    rating_lines = _render_rating_block(rating=client_rating, reviews=client_reviews)
    if rating_lines:
        parts.extend(rating_lines)
        parts.append("")

    parts.append("👉 Toque no botão abaixo para abrir:")
    return "\n".join(parts).strip()

def _render_basic_message(title: str, matched_kw: str) -> str:
    return (
        "💼 <b>Novo projeto disponível!</b>\n\n"
        f"🎯 <b>Match:</b> <code>{esc(matched_kw)}</code>\n"
        f"🧾 <b>Título:</b> {esc(title)}\n\n"
        "👉 Toque no botão abaixo para abrir:"
    )


# ===================== enriquecimento =====================

def _enrich_project(link: str) -> Dict[str, object] | None:
    """Tenta detalhe e listagem e mescla resultados."""
    is_99 = "99freelas" in (link or "").lower()
    detail_extra: Dict[str, object] | None = None
    list_extra: Dict[str, object] | None = None

    if is_99 and fetch_html and scrape_99freelas_detail:
        try:
            html = fetch_html(link)  # type: ignore[misc]
            if html:
                detail_extra = scrape_99freelas_detail(html)  # type: ignore[misc]
        except Exception as e:
            logger.info("[notifier] enrich detalhe falhou para link=%s: %s", link, e)

    if is_99 and enrich_from_list_pages:
        try:
            pid = _project_id_from_link(link)
            if pid:
                list_extra = enrich_from_list_pages(pid, pages=6)  # type: ignore[misc]
        except Exception as e:
            logger.info("[notifier] enrich listagem falhou para link=%s: %s", link, e)

    merged = _merge_enrich(detail_extra, list_extra)
    if merged and any(v not in (None, "", {}) for v in merged.values()):
        logger.debug("[notifier] enrich merged=%s", merged)
        return merged
    return None


# ===================== dados do banco =====================

def _extract_db_extra(ppu) -> Dict[str, object] | None:
    """
    Extrai metadados ricos diretamente do ProjectGlobal associado ao ppu.
    Retorna None se o projeto não tem campos enriquecidos (registros antigos).
    Não faz chamadas HTTP — usa apenas o que já está no banco.
    """
    gp = getattr(ppu, "global_project", None)
    if gp is None:
        return None

    age_min: int | None = None
    pub = getattr(gp, "published_at", None)
    if pub is not None:
        try:
            now = datetime.now(timezone.utc)
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            delta = now - pub
            age_min = max(0, int(delta.total_seconds() / 60))
        except Exception:
            age_min = None

    fields: Dict[str, object] = {
        "category":      getattr(gp, "category", None),
        "level":         getattr(gp, "level", None),
        "age_minutes":   age_min,
        "proposals":     getattr(gp, "proposals", None),
        "interested":    getattr(gp, "interested", None),
        "client_rating": getattr(gp, "client_rating", None),
        "client_reviews":getattr(gp, "client_reviews", None),
    }

    # Só retorna se ao menos um campo de metadado (além de age_minutes) está preenchido
    has_meta = any(
        fields[k] is not None
        for k in ("category", "level", "proposals", "interested", "client_rating", "client_reviews")
    )
    return fields if has_meta else None


# ===================== fluxo principal =====================

def _build_message_for_project(ppu) -> str:
    title      = ppu.title or "Projeto"
    link       = ppu.link or ""
    matched_kw = ppu.matched_keyword or ""

    # 1ª tentativa: dados já persistidos no banco (sem chamada HTTP)
    extra = _extract_db_extra(ppu)

    # 2ª tentativa: enriquecimento via HTTP (funciona apenas em IP residencial)
    if not extra:
        extra = _enrich_project(link)

    if extra:
        return _render_rich_message(title=title, link=link, matched_kw=matched_kw, extra=extra)
    return _render_basic_message(title, matched_kw)

def notify_pending(max_batch: int = 100) -> int:
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

            # Verifica limite diário do plano antes de enviar
            if not can_receive_alert_today(db, ppu.user_id):
                logger.info(
                    "[notifier] user_id=%s atingiu limite diário de alertas do plano. "
                    "Notificação adiada para amanhã.",
                    ppu.user_id,
                )
                continue  # mantém pendente; será reprocessado no próximo ciclo/dia

            text = _build_message_for_project(ppu)
            ok = send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=_button_open(ppu.link),
            )

            if ok:
                mark_project_notified(db, ppu)
                increment_alert_count(db, ppu.user_id)
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
