"""Centralised configuration loaded from the environment (.env).

Everything reads config from here so there is one place to reason about secrets
and toggles. Values are loaded once at import time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time

from dotenv import load_dotenv

# Load .env from the repo root if present. In production (systemd/launchd) the
# environment is usually injected directly; load_dotenv is a no-op then.
load_dotenv()


def _get(key: str, default: str | None = None) -> str | None:
    val = os.environ.get(key, default)
    if val is not None:
        val = val.strip()
    return val or default


def _get_int(key: str, default: int) -> int:
    raw = _get(key)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _parse_hhmm(raw: str | None, default: time) -> time:
    if not raw:
        return default
    try:
        hh, mm = raw.split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return default


@dataclass(frozen=True)
class Settings:
    # Discord
    discord_bot_token: str | None = field(default_factory=lambda: _get("DISCORD_BOT_TOKEN"))
    discord_guild_id: str | None = field(default_factory=lambda: _get("DISCORD_GUILD_ID"))

    # People
    owner_discord_user_id: str | None = field(
        default_factory=lambda: _get("OWNER_DISCORD_USER_ID")
    )
    partner_discord_user_id: str | None = field(
        default_factory=lambda: _get("PARTNER_DISCORD_USER_ID")
    )
    partner_display_name: str | None = field(
        default_factory=lambda: _get("PARTNER_DISPLAY_NAME")
    )

    # Supabase
    supabase_url: str | None = field(default_factory=lambda: _get("SUPABASE_URL"))
    supabase_anon_key: str | None = field(default_factory=lambda: _get("SUPABASE_ANON_KEY"))
    supabase_service_role_key: str | None = field(
        default_factory=lambda: _get("SUPABASE_SERVICE_ROLE_KEY")
    )

    # Agent
    agent_mode: str = field(default_factory=lambda: _get("AGENT_MODE", "cli"))
    claude_bin: str = field(default_factory=lambda: _get("CLAUDE_BIN", "claude"))

    # Scheduler / locale
    timezone: str = field(default_factory=lambda: _get("TIMEZONE", "America/Phoenix"))
    briefing_time: time = field(
        default_factory=lambda: _parse_hhmm(_get("BRIEFING_TIME"), time(7, 0))
    )
    weekly_recap_dow: int = field(default_factory=lambda: _get_int("WEEKLY_RECAP_DOW", 6))
    weekly_recap_time: time = field(
        default_factory=lambda: _parse_hhmm(_get("WEEKLY_RECAP_TIME"), time(18, 0))
    )
    closeout_grace_min: int = field(default_factory=lambda: _get_int("CLOSEOUT_GRACE_MIN", 15))
    nightly_nudge_time: time = field(
        default_factory=lambda: _parse_hhmm(_get("NIGHTLY_NUDGE_TIME"), time(21, 0))
    )

    # Dashboard
    dashboard_host: str = field(default_factory=lambda: _get("DASHBOARD_HOST", "127.0.0.1"))
    dashboard_port: int = field(default_factory=lambda: _get_int("DASHBOARD_PORT", 5000))
    dashboard_secret: str | None = field(default_factory=lambda: _get("DASHBOARD_SECRET"))

    # Hub
    hub_os: str = field(default_factory=lambda: _get("HUB_OS", "linux"))
    log_level: str = field(default_factory=lambda: _get("LOG_LEVEL", "INFO"))

    def require(self, *names: str) -> None:
        """Raise if any named setting is missing — call at startup of a surface
        that needs them (bot, dashboard, seed)."""
        missing = [n for n in names if not getattr(self, n, None)]
        if missing:
            raise RuntimeError(
                "Missing required settings: "
                + ", ".join(missing)
                + ". Fill them in .env (see .env.example)."
            )


settings = Settings()
