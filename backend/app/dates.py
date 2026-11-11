"""Business date helpers. Precomputes dates for relative phrases (today, yesterday, this month...) for the LLM."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .config import settings


def now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


def business_today() -> date:
    """Times before the business-day cut-off (e.g. 2 AM) count towards the previous day."""
    if settings.as_of_date.strip():
        return date.fromisoformat(settings.as_of_date.strip())
    return (now_local() - timedelta(hours=settings.business_day_start_hour)).date()


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _prev_month_range(d: date) -> tuple[date, date]:
    last = _month_start(d) - timedelta(days=1)
    return _month_start(last), last


def _fy_start(d: date) -> date:
    return date(d.year if d.month >= 4 else d.year - 1, 4, 1)


def date_reference() -> dict[str, str]:
    t = business_today()
    y = t - timedelta(days=1)
    week_start = t - timedelta(days=t.weekday())               # Monday
    lw_start, lw_end = week_start - timedelta(days=7), week_start - timedelta(days=1)
    lm_start, lm_end = _prev_month_range(t)
    fy = _fy_start(t)
    return {
        "today": f"{t} ({t:%A})",
        "yesterday": f"{y} ({y:%A})",
        "same day last week": f"{t - timedelta(days=7)} ({(t - timedelta(days=7)):%A})",
        "this week (Mon-today)": f"{week_start} to {t}",
        "last week (Mon-Sun)": f"{lw_start} to {lw_end}",
        "last 7 days": f"{t - timedelta(days=6)} to {t}",
        "last 30 days": f"{t - timedelta(days=29)} to {t}",
        "this month (till today)": f"{_month_start(t)} to {t}",
        "last month": f"{lm_start} to {lm_end}",
        "this financial year (Apr-Mar, till today)": f"{fy} to {t}",
    }


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD, got '{value}'") from exc
