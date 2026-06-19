"""Schedule blocks + the timecard (block_logs).

The timecard model (handoff 5.3):
  open -> closed (finish_time + completed) | unclosed (mismanaged) | excluded
One block_log row per block-instance per day, unique on (block_id, date).
"""
from __future__ import annotations

from datetime import date, datetime

from db.client import db


# --- Blocks -----------------------------------------------------------------


def list_blocks(active_only: bool = True) -> list[dict]:
    q = db().table("schedule_blocks").select("*").order("start_at")
    if active_only:
        q = q.eq("active", True)
    return q.execute().data


def get_block(block_id: str) -> dict | None:
    res = db().table("schedule_blocks").select("*").eq("id", block_id).limit(1).execute()
    return res.data[0] if res.data else None


def add_block(
    label: str,
    category: str | None = None,
    goal: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
    recurring_rule: str | None = None,
) -> dict:
    row = {
        "label": label,
        "category": category,
        "goal": goal,
        "start_at": start_at,
        "end_at": end_at,
        "recurring_rule": recurring_rule,
    }
    return db().table("schedule_blocks").insert(row).execute().data[0]


def update_block(block_id: str, **fields) -> dict:
    allowed = {"label", "category", "goal", "start_at", "end_at", "recurring_rule", "active"}
    patch = {k: v for k, v in fields.items() if k in allowed}
    return db().table("schedule_blocks").update(patch).eq("id", block_id).execute().data[0]


# --- Timecard (block_logs) --------------------------------------------------


def get_log(block_id: str, on: date) -> dict | None:
    res = (
        db()
        .table("block_logs")
        .select("*")
        .eq("block_id", block_id)
        .eq("date", on.isoformat())
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def ensure_log(block_id: str, on: date, state: str = "open") -> dict:
    """Create the day's log row if missing (idempotent on (block_id, date))."""
    existing = get_log(block_id, on)
    if existing:
        return existing
    row = {"block_id": block_id, "date": on.isoformat(), "state": state}
    return db().table("block_logs").upsert(row, on_conflict="block_id,date").execute().data[0]


def close_log(
    block_id: str,
    on: date,
    completed: bool,
    closed_by: str | None = None,
    finish_time: datetime | None = None,
) -> dict:
    patch = {
        "state": "closed",
        "completed": completed,
        "closed_by": closed_by,
        "finish_time": (finish_time or datetime.now().astimezone()).isoformat(),
    }
    ensure_log(block_id, on)
    return (
        db()
        .table("block_logs")
        .update(patch)
        .eq("block_id", block_id)
        .eq("date", on.isoformat())
        .execute()
        .data[0]
    )


def mark_unclosed(block_id: str, on: date) -> dict:
    """Mark an unanswered close-out as unclosed (reads as mismanaged time)."""
    log = ensure_log(block_id, on)
    if log["state"] in ("closed", "excluded"):
        return log
    return (
        db()
        .table("block_logs")
        .update({"state": "unclosed"})
        .eq("block_id", block_id)
        .eq("date", on.isoformat())
        .execute()
        .data[0]
    )


def exclude_log(block_id: str, on: date) -> dict:
    """Exclude a block-instance from analytics (day-off)."""
    ensure_log(block_id, on)
    return (
        db()
        .table("block_logs")
        .update({"state": "excluded"})
        .eq("block_id", block_id)
        .eq("date", on.isoformat())
        .execute()
        .data[0]
    )


def logs_between(start: date, end: date) -> list[dict]:
    return (
        db()
        .table("block_logs")
        .select("*, block:schedule_blocks(id,label,category,goal)")
        .gte("date", start.isoformat())
        .lte("date", end.isoformat())
        .execute()
        .data
    )


def open_logs_before(cutoff_date: date) -> list[dict]:
    """Open/blank logs that should be nudged for backfill."""
    return (
        db()
        .table("block_logs")
        .select("*, block:schedule_blocks(id,label)")
        .lte("date", cutoff_date.isoformat())
        .in_("state", ["open", "unclosed"])
        .execute()
        .data
    )
