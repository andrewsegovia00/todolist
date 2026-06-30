"""Channel -> mode routing (handoff 5.8).

On each message: look up channel_config by channel_id -> resolve mode -> load the
mode's system prompt + enabled tools -> invoke the agent only if the turn needs
it. A session per channel keeps context separate.
"""
from __future__ import annotations

import os

from core.logging_config import get_logger
from agent import runner
from bot.services import ideas_flow
from db.repos import config_repo, events_repo

log = get_logger("bot.router")

# session_id per channel, so each channel keeps its own agent context.
_sessions: dict[str, str] = {}

_MCP_CONFIG = os.path.join(os.path.dirname(__file__), "..", "agent", "mcp_config.json")


def mode_for_channel(channel_id: str) -> str | None:
    cfg = config_repo.get_channel_mode(str(channel_id))
    return cfg["mode"] if cfg else None


async def handle_fuzzy_turn(channel_id: str, mode: str, user_message: str, actor: str | None) -> str:
    """Route a free-form message and return a reply.

    #ideas runs the hybrid capture/recall flow (bot persists, agent phrases).
    Other modes get a terse agent reply (no DB writes — those are deterministic
    or handled via the dashboard).
    """
    mcp = os.path.abspath(_MCP_CONFIG)

    if mode == "ideas":
        reply_text = await ideas_flow.handle(channel_id, user_message, actor, mcp)
    else:
        session_id = _sessions.get(str(channel_id))
        reply = await runner.ask(
            user_message=user_message, mode=mode, session_id=session_id, mcp_config_path=mcp
        )
        if reply.session_id:
            _sessions[str(channel_id)] = reply.session_id
        data = ideas_flow.extract_json(reply.text) or {}
        reply_text = data.get("reply") or reply.text

    # Audit trail -> #agent-log
    try:
        events_repo.log_event(
            type="agent_turn",
            payload={"mode": mode, "channel_id": str(channel_id), "prompt": user_message[:500]},
            actor=actor,
        )
    except Exception:  # logging must never break the reply
        log.exception("Failed to write agent_turn event")

    return reply_text
