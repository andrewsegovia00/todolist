"""Editable config: buckets, projects, statuses, tags, settings, channel routing.

"Config is data, not code" (architecture Section 2) — everything here is edited
at runtime via #config or the dashboard, never by changing source.
"""
from __future__ import annotations

from db.client import db

# --- Buckets ----------------------------------------------------------------


def list_buckets(active_only: bool = True) -> list[dict]:
    q = db().table("buckets").select("*").order("name")
    if active_only:
        q = q.eq("active", True)
    return q.execute().data


def add_bucket(name: str, description: str | None = None) -> dict:
    res = db().table("buckets").insert({"name": name, "description": description}).execute()
    return res.data[0]


def rename_bucket(bucket_id: str, new_name: str) -> dict:
    res = db().table("buckets").update({"name": new_name}).eq("id", bucket_id).execute()
    return res.data[0]


def archive_bucket(bucket_id: str) -> dict:
    res = db().table("buckets").update({"active": False}).eq("id", bucket_id).execute()
    return res.data[0]


def get_bucket_by_name(name: str) -> dict | None:
    res = db().table("buckets").select("*").ilike("name", name).limit(1).execute()
    return res.data[0] if res.data else None


# --- Projects ---------------------------------------------------------------


def list_projects(active_only: bool = True) -> list[dict]:
    q = db().table("projects").select("*").order("name")
    if active_only:
        q = q.eq("active", True)
    return q.execute().data


def add_project(name: str, description: str | None = None) -> dict:
    res = db().table("projects").insert({"name": name, "description": description}).execute()
    return res.data[0]


def rename_project(project_id: str, new_name: str) -> dict:
    res = db().table("projects").update({"name": new_name}).eq("id", project_id).execute()
    return res.data[0]


def archive_project(project_id: str) -> dict:
    res = db().table("projects").update({"active": False}).eq("id", project_id).execute()
    return res.data[0]


def get_project_by_name(name: str) -> dict | None:
    res = db().table("projects").select("*").ilike("name", name).limit(1).execute()
    return res.data[0] if res.data else None


# --- Statuses ---------------------------------------------------------------


def list_statuses(active_only: bool = True) -> list[dict]:
    q = db().table("statuses").select("*").order("sort_order")
    if active_only:
        q = q.eq("active", True)
    return q.execute().data


def get_status_by_name(name: str) -> dict | None:
    res = db().table("statuses").select("*").ilike("name", name).limit(1).execute()
    return res.data[0] if res.data else None


def get_default_status() -> dict | None:
    """The first status in the pipeline (e.g. 'Idea')."""
    res = db().table("statuses").select("*").eq("active", True).order("sort_order").limit(1).execute()
    return res.data[0] if res.data else None


# --- Tags -------------------------------------------------------------------


def list_tags() -> list[dict]:
    return db().table("tags").select("*").order("name").execute().data


def get_or_create_tag(name: str) -> dict:
    existing = db().table("tags").select("*").ilike("name", name).limit(1).execute()
    if existing.data:
        return existing.data[0]
    return db().table("tags").insert({"name": name}).execute().data[0]


def rename_tag(tag_id: str, new_name: str) -> dict:
    return db().table("tags").update({"name": new_name}).eq("id", tag_id).execute().data[0]


# --- Settings (key/value global toggles) ------------------------------------


def get_setting(key: str, default: str | None = None) -> str | None:
    res = db().table("settings").select("value").eq("key", key).limit(1).execute()
    return res.data[0]["value"] if res.data else default


def set_setting(key: str, value: str) -> dict:
    res = db().table("settings").upsert({"key": key, "value": value}, on_conflict="key").execute()
    return res.data[0]


def checkins_enabled() -> bool:
    return (get_setting("checkins_enabled", "true") or "true").lower() == "true"


# --- Channel routing --------------------------------------------------------


def get_channel_mode(channel_id: str) -> dict | None:
    res = (
        db()
        .table("channel_config")
        .select("*")
        .eq("channel_id", str(channel_id))
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def set_channel_mode(channel_id: str, mode: str, system_prompt_ref: str | None = None) -> dict:
    row = {
        "channel_id": str(channel_id),
        "mode": mode,
        "system_prompt_ref": system_prompt_ref or mode,
    }
    return db().table("channel_config").upsert(row, on_conflict="channel_id").execute().data[0]


def list_channel_config() -> list[dict]:
    return db().table("channel_config").select("*").execute().data
