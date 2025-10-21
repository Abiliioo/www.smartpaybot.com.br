# infrastructure/timeutils.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional
from .config import get_settings

def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().TZ_NAME)

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_local(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        # assume UTC se vier naive (não deve, mas garante)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz())

def fmt_br(dt: Optional[datetime], with_secs: bool = False) -> str:
    d = to_local(dt)
    if not d:
        return "-"
    fmt = "%d/%m/%Y %H:%M:%S" if with_secs else "%d/%m/%Y %H:%M"
    return d.strftime(fmt)
