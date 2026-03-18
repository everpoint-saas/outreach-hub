from __future__ import annotations

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo


US_EASTERN = ZoneInfo("America/New_York")
OPTIMAL_WEEKDAYS = {1, 2, 3}  # Tue, Wed, Thu
WINDOW_START_HOUR = 9
WINDOW_END_HOUR = 11


def now_est() -> datetime:
    return datetime.now(US_EASTERN)


def is_optimal_send_time(dt: datetime | None = None) -> bool:
    current = dt.astimezone(US_EASTERN) if dt else now_est()
    if current.isoweekday() not in OPTIMAL_WEEKDAYS:
        return False
    return WINDOW_START_HOUR <= current.hour < WINDOW_END_HOUR


def next_optimal_send_time(dt: datetime | None = None) -> datetime:
    current = dt.astimezone(US_EASTERN) if dt else now_est()

    if is_optimal_send_time(current):
        return current

    candidate = current
    for _ in range(14):
        if candidate.isoweekday() in OPTIMAL_WEEKDAYS:
            slot = datetime.combine(candidate.date(), time(hour=WINDOW_START_HOUR), tzinfo=US_EASTERN)
            if slot > current:
                return slot
        candidate = candidate + timedelta(days=1)

    fallback = current + timedelta(days=1)
    return datetime.combine(fallback.date(), time(hour=WINDOW_START_HOUR), tzinfo=US_EASTERN)

