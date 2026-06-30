"""Hybrid #ideas capture + recall.

The bot owns the database; the agent only classifies intent and phrases a short
reply. Every capture is persisted by Python with the raw text preserved, so an
idea is never silently lost even if the agent is slow, offline, or returns junk.
"""
from __future__ import annotations

import json
import re

from core.logging_config import get_logger
from agent import runner
from db.repos import config_repo, ideas_repo, people_repo

log = get_logger("bot.ideas_flow")

# Per-channel memory for follow-ups.
_last_idea: dict[str, str] = {}
_pending_split: dict[str, list[str]] = {}
_sessions: dict[str, str] = {}


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of an agent reply, tolerating code fences
    or stray prose. Returns None if nothing parses."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _provisional_title(text: str, limit: int = 70) -> str:
    first = text.strip().splitlines()[0].strip() if text.strip() else "Untitled"
    return (first[: limit - 1] + "…") if len(first) > limit else first


def _author_id(actor: str | None) -> str | None:
    if actor:
        p = people_repo.get_by_discord_id(actor)
        if p:
            return p["id"]
    owner = people_repo.get_owner()
    return owner["id"] if owner else None


def _save(title: str, notes: str, actor: str | None) -> dict:
    return ideas_repo.create_idea(title=title[:70], notes=notes, author_id=_author_id(actor))


async def handle(
    channel_id: str, user_message: str, actor: str | None, mcp_config_path: str | None = None
) -> str:
    cid = str(channel_id)
    low = user_message.strip().lower()

    # --- deterministic follow-ups (no model call) ---
    if low in ("split", "/split") and _pending_split.get(cid):
        items = _pending_split.pop(cid)
        if _last_idea.get(cid):
            ideas_repo.update_idea(_last_idea[cid], title=items[0][:70])
        for extra in items[1:]:
            _save(extra, extra, actor)
        return "Split into %d ideas: %s" % (len(items), ", ".join(f"**{i[:60]}**" for i in items))

    if low.startswith(("rename:", "title:")) and _last_idea.get(cid):
        new_title = user_message.split(":", 1)[1].strip()
        if new_title:
            ideas_repo.update_idea(_last_idea[cid], title=new_title[:70])
            return f"Renamed to **{new_title[:70]}**."

    # --- agent: classify + phrase (returns compact JSON) ---
    buckets = ", ".join(b["name"] for b in config_repo.list_buckets()) or "(none)"
    reply = await runner.ask(
        user_message=user_message,
        mode="ideas",
        session_id=_sessions.get(cid),
        mcp_config_path=mcp_config_path,
        context={"buckets": buckets},
    )
    if reply.session_id:
        _sessions[cid] = reply.session_id
    data = extract_json(reply.text) or {}
    intent = (data.get("intent") or "capture").lower()

    if intent == "recall":
        b = config_repo.get_bucket_by_name(data["bucket"]) if data.get("bucket") else None
        p = config_repo.get_project_by_name(data["project"]) if data.get("project") else None
        titles = ideas_repo.list_titles(
            bucket_id=b["id"] if b else None, project_id=p["id"] if p else None
        )
        if not titles:
            return "No matching ideas."
        head = "Ideas" + (f" in {data['bucket']}" if data.get("bucket") else "")
        return f"**{head}:**\n" + "\n".join(
            f"• {t['title']}  _({t['status'] or '—'})_" for t in titles[:40]
        )

    if intent == "detail" and data.get("target"):
        idea = ideas_repo.find_by_title(data["target"])
        if not idea:
            return f"Couldn't find an idea matching “{data['target']}”."
        notes = (idea.get("notes") or "").strip() or "(no notes)"
        return f"**{idea['title']}**\n{notes[:1500]}"

    if intent == "other" and not data.get("items") and not data.get("title"):
        return data.get("reply") or "👍"

    # --- capture (default + safe fallback if JSON failed) ---
    items = [i for i in (data.get("items") or []) if i]
    title = data.get("title") or _provisional_title(user_message)
    idea = _save(title, user_message, actor)
    _last_idea[cid] = idea["id"]
    _pending_split.pop(cid, None)

    msg = f"Saved ✅ **{idea['title']}** to Ideas."
    if data.get("reply"):
        msg += f"\n{data['reply']}"
    if len(items) > 1:
        _pending_split[cid] = items
        msg += f"\nThis looks like **{len(items)}** separate ideas — reply `split` to file them individually."
    return msg
