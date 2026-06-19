"""People lookups."""
from __future__ import annotations

from db.client import db


def get_by_discord_id(discord_user_id: str) -> dict | None:
    res = (
        db()
        .table("people")
        .select("*")
        .eq("discord_user_id", str(discord_user_id))
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def list_people() -> list[dict]:
    return db().table("people").select("*").order("role").execute().data


def get_owner() -> dict | None:
    res = db().table("people").select("*").eq("role", "owner").limit(1).execute()
    return res.data[0] if res.data else None
