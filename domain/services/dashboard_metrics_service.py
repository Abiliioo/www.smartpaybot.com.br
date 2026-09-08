from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from statistics import median
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from domain.models import ProjectGlobal, ProjectPerUser, User, UserKeyword


BR_TZ_NAME = "America/Sao_Paulo"


@dataclass(frozen=True)
class DateWindow:
    start_utc: datetime
    end_utc: datetime


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _local_day_start(now: datetime | None = None, *, tz_name: str = BR_TZ_NAME) -> datetime:
    tz = ZoneInfo(tz_name)
    current = _as_utc(now or datetime.now(timezone.utc)).astimezone(tz)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def _utc_window_for_local_days(start_day: date, days: int, *, tz_name: str = BR_TZ_NAME) -> DateWindow:
    tz = ZoneInfo(tz_name)
    start_local = datetime.combine(start_day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=days)
    return DateWindow(start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc))


def _pct_delta(current: int, previous: int) -> int | None:
    if previous == 0:
        return None
    return int(round(((current - previous) / previous) * 100))


def _count_between(rows: Iterable[datetime], start: datetime, end: datetime) -> int:
    return sum(1 for dt in rows if start <= dt < end)


def _daily_series(rows: Iterable[datetime], *, start_day: date, days: int, tz_name: str) -> list[dict]:
    buckets = {start_day + timedelta(days=i): 0 for i in range(days)}
    tz = ZoneInfo(tz_name)
    for dt in rows:
        day = _as_utc(dt).astimezone(tz).date()
        if day in buckets:
            buckets[day] += 1
    return [{"date": day.isoformat(), "count": buckets[day]} for day in sorted(buckets)]


def _recent_project_item(row) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "matched_keyword": row.matched_keyword,
        "created_at": row.created_at,
        "link": row.link,
    }


def build_dashboard_metrics(
    db: Session,
    *,
    user: User,
    plan: dict,
    now: datetime | None = None,
    tz_name: str = BR_TZ_NAME,
) -> dict:
    uid = int(user.id)
    today_start_local = _local_day_start(now, tz_name=tz_name)
    today = today_start_local.date()
    yesterday = today - timedelta(days=1)
    start_7d = today - timedelta(days=6)
    previous_7d_start = start_7d - timedelta(days=7)
    start_30d = today - timedelta(days=29)

    widest_window = _utc_window_for_local_days(start_30d, 30, tz_name=tz_name)
    previous_window = _utc_window_for_local_days(previous_7d_start, 7, tz_name=tz_name)
    current_window = _utc_window_for_local_days(start_7d, 7, tz_name=tz_name)
    today_window = _utc_window_for_local_days(today, 1, tz_name=tz_name)
    yesterday_window = _utc_window_for_local_days(yesterday, 1, tz_name=tz_name)

    project_rows = db.execute(
        select(ProjectPerUser.created_at, ProjectPerUser.matched_keyword)
        .where(
            ProjectPerUser.user_id == uid,
            ProjectPerUser.created_at >= widest_window.start_utc,
            ProjectPerUser.created_at < widest_window.end_utc,
        )
    ).all()
    created_at_rows = [_as_utc(row.created_at) for row in project_rows]

    opportunities_today = _count_between(created_at_rows, today_window.start_utc, today_window.end_utc)
    opportunities_yesterday = _count_between(
        created_at_rows, yesterday_window.start_utc, yesterday_window.end_utc
    )
    opportunities_7d = _count_between(created_at_rows, current_window.start_utc, current_window.end_utc)
    opportunities_prev_7d = _count_between(
        created_at_rows, previous_window.start_utc, previous_window.end_utc
    )

    active_keyword_rows = db.execute(
        select(UserKeyword.keyword, UserKeyword.created_at)
        .where(UserKeyword.user_id == uid)
        .order_by(UserKeyword.created_at.asc(), UserKeyword.keyword.asc())
    ).all()
    active_keywords = {row.keyword for row in active_keyword_rows}

    keyword_counts: dict[str, int] = {}
    for row in project_rows:
        keyword = row.matched_keyword
        if not keyword:
            continue
        keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

    productive_active_keywords = {
        keyword for keyword, count in keyword_counts.items() if count > 0 and keyword in active_keywords
    }
    ranking_30d = [
        {"keyword": keyword, "matches": count, "active": keyword in active_keywords}
        for keyword, count in sorted(keyword_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    ]

    seven_day_matches = {
        row.matched_keyword
        for row in project_rows
        if row.matched_keyword and current_window.start_utc <= _as_utc(row.created_at) < current_window.end_utc
    }
    zero_result_mature = []
    for row in active_keyword_rows:
        if _as_utc(row.created_at) <= current_window.start_utc and row.keyword not in seven_day_matches:
            zero_result_mature.append(row.keyword)

    latency_rows = db.execute(
        select(ProjectPerUser.notified_at, ProjectGlobal.published_at)
        .join(ProjectGlobal, ProjectPerUser.global_project_id == ProjectGlobal.id)
        .where(
            ProjectPerUser.user_id == uid,
            ProjectPerUser.notified_at.is_not(None),
            ProjectPerUser.notified_at >= current_window.start_utc,
            ProjectPerUser.notified_at < current_window.end_utc,
        )
    ).all()
    latency_samples_seconds = []
    for row in latency_rows:
        if row.notified_at is None or row.published_at is None:
            continue
        delta_seconds = int((_as_utc(row.notified_at) - _as_utc(row.published_at)).total_seconds())
        if delta_seconds >= 0:
            latency_samples_seconds.append(delta_seconds)

    latency_denominator = len(latency_rows)
    latency_coverage_pct = (
        int(round((len(latency_samples_seconds) / latency_denominator) * 100)) if latency_denominator else None
    )
    latency_median_seconds = int(median(latency_samples_seconds)) if latency_samples_seconds else None
    latency_median_minutes = round(latency_median_seconds / 60, 1) if latency_median_seconds is not None else None

    alerts_sent_today = int(
        db.execute(
            select(func.count())
            .select_from(ProjectPerUser)
            .where(
                ProjectPerUser.user_id == uid,
                ProjectPerUser.notified_at.is_not(None),
                ProjectPerUser.notified_at >= today_window.start_utc,
                ProjectPerUser.notified_at < today_window.end_utc,
            )
        ).scalar_one()
        or 0
    )

    won_30d_filter = and_(
        ProjectPerUser.won_at >= widest_window.start_utc,
        ProjectPerUser.won_at < widest_window.end_utc,
    )
    won_summary = db.execute(
        select(
            func.count(ProjectPerUser.id),
            func.coalesce(func.sum(ProjectPerUser.won_cents), 0),
            func.coalesce(func.sum(case((won_30d_filter, 1), else_=0)), 0),
            func.coalesce(
                func.sum(case((won_30d_filter, ProjectPerUser.won_cents), else_=0)),
                0,
            ),
        )
        .where(ProjectPerUser.user_id == uid, ProjectPerUser.won.is_(True))
    ).one()

    return {
        "status": {
            "monitoring_active": bool(user.bot_active),
            "telegram_connected": bool(user.chat_id),
            "plan_name": str(plan.get("name") or "Gratuito"),
            "plan_slug": str(plan.get("slug") or "free"),
        },
        "kpis": {
            "opportunities_today": opportunities_today,
            "opportunities_yesterday": opportunities_yesterday,
            "opportunities_7d": opportunities_7d,
            "opportunities_prev_7d": opportunities_prev_7d,
            "opportunities_7d_delta": opportunities_7d - opportunities_prev_7d,
            "opportunities_7d_pct": _pct_delta(opportunities_7d, opportunities_prev_7d),
            "alert_latency_median_seconds": latency_median_seconds,
            "alert_latency_median_minutes": latency_median_minutes,
            "alert_latency_sample_count": len(latency_samples_seconds),
            "alert_latency_coverage_pct": latency_coverage_pct,
            "productive_keywords": len(productive_active_keywords),
            "keywords_total": len(active_keywords),
        },
        "series": {
            "7d": _daily_series(created_at_rows, start_day=start_7d, days=7, tz_name=tz_name),
            "30d": _daily_series(created_at_rows, start_day=start_30d, days=30, tz_name=tz_name),
        },
        "keywords": {
            "ranking_30d": ranking_30d,
            "productive_count_30d": len(productive_active_keywords),
            "total_active": len(active_keywords),
            "zero_result_mature_count": len(zero_result_mature),
            "zero_result_mature": zero_result_mature[:5],
        },
        "results": {
            "won_total": int(won_summary[0] or 0),
            "won_30d": int(won_summary[2] or 0),
            "won_value_total_cents": int(won_summary[1] or 0),
            "won_value_30d_cents": int(won_summary[3] or 0),
        },
        "alerts": {
            "sent_today": alerts_sent_today,
        },
        "recent_projects": [
            _recent_project_item(row)
            for row in db.execute(
                select(
                    ProjectPerUser.id,
                    ProjectPerUser.title,
                    ProjectPerUser.matched_keyword,
                    ProjectPerUser.created_at,
                    ProjectPerUser.link,
                )
                .where(ProjectPerUser.user_id == uid)
                .order_by(ProjectPerUser.created_at.desc(), ProjectPerUser.id.desc())
                .limit(3)
            ).all()
        ],
        "legacy": {
            "review_count_is_partial_not_won": True,
        },
    }
