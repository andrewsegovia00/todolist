"""Day-off / pause windows (handoff 5.4).

Off = excluded from analytics, not merely silenced.
"""
from __future__ import annotations

from datetime import date, datetime, time

from db.client import db


def add_day_off(start_at: datetime, end_at: datetime, reason: str | None = None,
                person_id: str | None = None) -> dict:
    row = {
        "person_id": person_id,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "reason": reason,
    }
    return db().table("day_off").insert(row).execute().data[0]


def windows_covering(on: date) -> list[dict]:
    """Day-off windows that overlap the given date."""
    day_start = datetime.combine(on, time.min).astimezone().isoformat()
    day_end = datetime.combine(on, time.max).astimezone().isoformat()
    return (
        db()
        .table("day_off")
        .select("*")
        .lte("start_at", day_end)
        .gte("end_at", day_start)
        .execute()
        .data
    )


def is_day_off(on: date) -> bool:
    return len(windows_covering(on)) > 0
