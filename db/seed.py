"""Seed the rows that depend on Phase-0 values (people, channel_config).

The static seed (buckets/projects/statuses/settings) lives in
`migrations/0003_seed.sql`. This script handles what can only be known at
provisioning time: the two people (from .env) and, optionally, channel routing.

Run:  python -m db.seed
"""
from __future__ import annotations

from core.logging_config import get_logger
from core.settings import settings
from db.client import db

log = get_logger("db.seed")


def seed_people() -> None:
    settings.require("owner_discord_user_id", "partner_discord_user_id")
    client = db()
    rows = [
        {
            "discord_user_id": settings.owner_discord_user_id,
            "name": settings.owner_display_name,
            "role": "owner",
        },
        {
            "discord_user_id": settings.partner_discord_user_id,
            "name": settings.partner_display_name,
            "role": "partner",
        },
    ]
    # Upsert on the unique discord_user_id so re-running is safe.
    client.table("people").upsert(rows, on_conflict="discord_user_id").execute()
    log.info("Seeded %d people.", len(rows))


def seed_channel_config() -> None:
    """Seed channel routing if CHANNEL_* ids are configured.

    Channel ids are not known until the Discord server exists, so this is
    optional and skipped silently when unset. You can also add routes at runtime
    via #config or the dashboard.
    """
    import os

    mapping = {
        "ideas": os.environ.get("CHANNEL_IDEAS"),
        "schedule": os.environ.get("CHANNEL_SCHEDULE"),
        "config": os.environ.get("CHANNEL_CONFIG"),
        "briefing": os.environ.get("CHANNEL_BRIEFING"),
        "log": os.environ.get("CHANNEL_AGENT_LOG"),
    }
    rows = [
        {"channel_id": cid.strip(), "mode": mode, "system_prompt_ref": mode}
        for mode, cid in mapping.items()
        if cid and cid.strip()
    ]
    if not rows:
        log.info("No CHANNEL_* env vars set; skipping channel_config seed.")
        return
    db().table("channel_config").upsert(rows, on_conflict="channel_id").execute()
    log.info("Seeded %d channel routes.", len(rows))


def main() -> None:
    seed_people()
    seed_channel_config()
    log.info("Seed complete.")


if __name__ == "__main__":
    main()
