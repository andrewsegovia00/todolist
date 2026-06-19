"""Dead-time task queue."""
from __future__ import annotations

from datetime import datetime

from db.client import db


def list_open(max_minutes: int | None = None) -> list[dict]:
    """Open tasks, highest priority first. If max_minutes given, only tasks that
    fit the window (or have no estimate)."""
    q = db().table("dead_time_tasks").select("*").eq("state", "open")
    rows = q.order("priority", desc=True).order("created_at").execute().data
    if max_minutes is None:
        return rows
    return [
        r
        for r in rows
        if r.get("duration_est_min") is None or r["duration_est_min"] <= max_minutes
    ]


def add_task(
    content: str,
    priority: int = 0,
    category: str | None = None,
    duration_est_min: int | None = None,
) -> dict:
    row = {
        "content": content,
        "priority": priority,
        "category": category,
        "duration_est_min": duration_est_min,
    }
    return db().table("dead_time_tasks").insert(row).execute().data[0]


def complete_task(task_id: str) -> dict:
    patch = {"state": "done", "done_at": datetime.now().astimezone().isoformat()}
    return db().table("dead_time_tasks").update(patch).eq("id", task_id).execute().data[0]
