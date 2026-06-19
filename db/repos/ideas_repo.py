"""Ideas CRUD + recall, plus tag joins.

Returns enriched rows (bucket/project/status/author names embedded) where useful
so callers don't re-query lookups.
"""
from __future__ import annotations

from db.client import db
from db.repos import config_repo

# Embed related names via PostgREST resource embedding.
_SELECT = (
    "*, bucket:buckets(id,name), project:projects(id,name), "
    "status:statuses(id,name,sort_order), author:people(id,name)"
)


def create_idea(
    title: str,
    notes: str | None = None,
    bucket_id: str | None = None,
    project_id: str | None = None,
    author_id: str | None = None,
    status_id: str | None = None,
) -> dict:
    if status_id is None:
        default = config_repo.get_default_status()
        status_id = default["id"] if default else None
    row = {
        "title": title,
        "notes": notes,
        "bucket_id": bucket_id,
        "project_id": project_id,
        "author_id": author_id,
        "status_id": status_id,
    }
    return db().table("ideas").insert(row).execute().data[0]


def get_idea(idea_id: str) -> dict | None:
    res = db().table("ideas").select(_SELECT).eq("id", idea_id).limit(1).execute()
    return res.data[0] if res.data else None


def find_by_title(title: str) -> dict | None:
    """Best-effort exact-ish title lookup for 'tell me about [title]'."""
    res = db().table("ideas").select(_SELECT).ilike("title", title).limit(1).execute()
    if res.data:
        return res.data[0]
    # fall back to fuzzy contains
    res = db().table("ideas").select(_SELECT).ilike("title", f"%{title}%").limit(1).execute()
    return res.data[0] if res.data else None


def update_idea(idea_id: str, **fields) -> dict:
    allowed = {"title", "notes", "bucket_id", "project_id", "status_id"}
    patch = {k: v for k, v in fields.items() if k in allowed}
    if not patch:
        return get_idea(idea_id)
    return db().table("ideas").update(patch).eq("id", idea_id).execute().data[0]


def set_status(idea_id: str, status_name: str) -> dict | None:
    status = config_repo.get_status_by_name(status_name)
    if not status:
        return None
    return update_idea(idea_id, status_id=status["id"])


def delete_idea(idea_id: str) -> None:
    db().table("ideas").delete().eq("id", idea_id).execute()


def list_ideas(
    bucket_id: str | None = None,
    project_id: str | None = None,
    status_id: str | None = None,
    author_id: str | None = None,
    tag_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    if tag_id:
        # Resolve ids through the join table first.
        joins = db().table("idea_tags").select("idea_id").eq("tag_id", tag_id).execute().data
        ids = [j["idea_id"] for j in joins]
        if not ids:
            return []
        q = db().table("ideas").select(_SELECT).in_("id", ids)
    else:
        q = db().table("ideas").select(_SELECT)
    if bucket_id:
        q = q.eq("bucket_id", bucket_id)
    if project_id:
        q = q.eq("project_id", project_id)
    if status_id:
        q = q.eq("status_id", status_id)
    if author_id:
        q = q.eq("author_id", author_id)
    return q.order("created_at", desc=True).limit(limit).execute().data


def list_titles(bucket_id: str | None = None, project_id: str | None = None) -> list[dict]:
    """Recall returns titles first (handoff 5.2)."""
    rows = list_ideas(bucket_id=bucket_id, project_id=project_id)
    return [{"id": r["id"], "title": r["title"], "status": (r.get("status") or {}).get("name")} for r in rows]


# --- Tag joins --------------------------------------------------------------


def add_tag(idea_id: str, tag_id: str) -> None:
    db().table("idea_tags").upsert(
        {"idea_id": idea_id, "tag_id": tag_id}, on_conflict="idea_id,tag_id"
    ).execute()


def remove_tag(idea_id: str, tag_id: str) -> None:
    db().table("idea_tags").delete().eq("idea_id", idea_id).eq("tag_id", tag_id).execute()


def actionable_ideas(limit: int = 10) -> list[dict]:
    """Ideas suitable to 'act on' in a dead-time window: early-pipeline ideas.

    Heuristic, deterministic: anything in the first two pipeline statuses.
    """
    statuses = config_repo.list_statuses()
    early_ids = [s["id"] for s in statuses[:2]]
    if not early_ids:
        return list_ideas(limit=limit)
    res = (
        db()
        .table("ideas")
        .select(_SELECT)
        .in_("status_id", early_ids)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data
