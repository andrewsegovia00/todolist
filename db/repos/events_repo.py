"""Event audit log -> #agent-log (handoff 4 'events')."""
from __future__ import annotations

from db.client import db


def log_event(type: str, payload: dict | None = None, actor: str | None = None) -> dict:
    row = {"type": type, "payload": payload or {}, "actor": actor}
    return db().table("events").insert(row).execute().data[0]


def recent(limit: int = 50) -> list[dict]:
    return (
        db()
        .table("events")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
