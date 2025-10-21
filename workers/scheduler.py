# workers/scheduler.py
from __future__ import annotations

import asyncio
import threading
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR  # <- listener

from infrastructure.logging import get_logger
from infrastructure.config import get_settings
from .ingestor import crawl_once
from .matcher import match_recent_projects
from .notifier import notify_pending

logger = get_logger(__name__)

_lock = threading.Lock()
_scheduler: Optional[BackgroundScheduler] = None


def _pipeline_tick():
    """Executa uma rodada: ingest -> match -> notify (sem sobreposição)."""
    if not _lock.acquire(blocking=False):
        logger.warning("[scheduler] tick ignorado: execução anterior ainda ativa.")
        return
    try:
        logger.info("[pipeline] início")
        settings = get_settings()

        # 1) Crawling (assíncrono)
        asyncio.run(crawl_once(pages=settings.SCAN_PAGES))

        # 2) Matching
        match_recent_projects()

        # 3) Notificação
        notify_pending()

        logger.info("[pipeline] fim")
    except Exception as e:
        logger.exception("[pipeline] falhou: %s", e)
        # opcional: raise para o APScheduler marcar como falha
        # raise
    finally:
        _lock.release()


def is_running() -> bool:
    return bool(_scheduler and _scheduler.running)


def _compute_interval():
    """
    Lê MIN/MAX do settings e devolve:
      base_seconds = SCAN_MIN_SECONDS (piso >= 60)
      jitter_seconds = max(0, SCAN_MAX_SECONDS - base)
      next_run_time = agora + random(0..jitter) (UTC)
    """
    s = get_settings()
    base = int(getattr(s, "SCAN_MIN_SECONDS", 180) or 180)
    base = max(60, base)  # piso de segurança
    maxv = int(getattr(s, "SCAN_MAX_SECONDS", base) or base)
    if maxv < base:
        maxv = base
    jitter = max(0, maxv - base)
    initial_delay = random.randint(0, jitter) if jitter else 0
    next_run = datetime.now(timezone.utc) + timedelta(seconds=initial_delay)
    return base, jitter, next_run, initial_delay


def _log_next_run(prefix: str = "[scheduler] próximo agendamento:") -> None:
    """Loga o próximo agendamento do job 'pipeline' (em horário local e ETA)."""
    global _scheduler
    if not _scheduler:
        return
    job = _scheduler.get_job("pipeline")
    if not job or not job.next_run_time:
        return
    nrt_local = job.next_run_time.astimezone()   # converte para timezone local
    now_local = datetime.now().astimezone()
    eta_sec = int((nrt_local - now_local).total_seconds())
    logger.info("%s %s (em ~%ss)", prefix, nrt_local.strftime("%Y-%m-%d %H:%M:%S %Z"), eta_sec)


def _on_job_event(event) -> None:
    """Listener chamado após cada execução (sucesso/erro) do job."""
    if event.job_id != "pipeline":
        return
    if event.exception:
        logger.error("[scheduler] job terminou com erro (id=%s).", event.job_id)
    _log_next_run("[scheduler] próximo após execução:")


def start(interval_seconds: int | None = None) -> bool:
    global _scheduler
    if is_running():
        logger.info("[scheduler] já está em execução.")
        return True

    settings = get_settings()
    every = interval_seconds or int(getattr(settings, "SCAN_MIN_SECONDS", 180) or 180)
    every = max(60, every)

    # >>> altera timezone do scheduler para o TZ do app
    _scheduler = BackgroundScheduler(timezone=ZoneInfo(settings.TZ_NAME))
    _scheduler.add_job(
        _pipeline_tick,
        IntervalTrigger(seconds=every),
        id="pipeline",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("[scheduler] iniciado: intervalo=%ss, tz=%s", every, settings.TZ_NAME)
    return True


def stop() -> bool:
    """Interrompe o scheduler (se estiver rodando)."""
    global _scheduler
    if _scheduler:
        try:
            _scheduler.remove_all_jobs()
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
            logger.info("[scheduler] parado.")
        finally:
            _scheduler = None
    return True


def run_once():
    """Executa uma rodada imediatamente (útil para testes)."""
    _pipeline_tick()


def start_scheduler():
    """
    Boot automático quando SCHEDULER_ENABLED=1 no .env.
    Agora usa MIN/MAX do .env (não força intervalo fixo).
    """
    s = get_settings()
    if not getattr(s, "SCHEDULER_ENABLED", False):
        logger.info("[scheduler] desabilitado por configuração (SCHEDULER_ENABLED=0).")
        return False
    return start(interval_seconds=None)


def stop_scheduler():
    return stop()
