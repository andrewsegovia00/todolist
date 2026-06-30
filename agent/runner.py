"""Invoke the subscription-authed Claude agent for fuzzy turns.

Two backends, selected by AGENT_MODE:
  - "cli": shell out to `claude -p` headless (default; needs only the CLI).
  - "sdk": Python Claude Agent SDK (import only if installed).

Both rely on Claude Code being logged into the Max account on the hub. The
guardrail (core.guardrails) ensures ANTHROPIC_API_KEY is unset so usage draws
from the subscription, never billed API.

A per-conversation session id keeps each Discord channel's context separate
(handoff 5.8). For the CLI backend we use `--resume <session_id>` when we have
one, and capture the new session id from the JSON output.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass

from core.logging_config import get_logger
from core.settings import settings
from agent import prompts

log = get_logger("agent.runner")


@dataclass
class AgentReply:
    text: str
    session_id: str | None = None


def _clean_env() -> dict[str, str]:
    """Environment for the agent subprocess with API-key vars stripped."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    return env


async def _run_cli(
    user_message: str,
    mode: str,
    session_id: str | None,
    mcp_config_path: str | None,
    context: dict | None = None,
) -> AgentReply:
    system_prompt = prompts.for_mode(mode, context)
    cmd = [
        settings.claude_bin,
        "-p",
        user_message,
        "--output-format",
        "json",
        "--append-system-prompt",
        system_prompt,
    ]
    if mcp_config_path and os.path.exists(mcp_config_path):
        cmd += ["--mcp-config", mcp_config_path]
    if session_id:
        cmd += ["--resume", session_id]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_clean_env(),
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        log.error("claude -p failed (%s): %s", proc.returncode, err)
        return AgentReply(text=f"(agent error) {err or 'claude -p failed'}", session_id=session_id)

    raw = stdout.decode(errors="replace").strip()
    try:
        data = json.loads(raw)
        # `claude -p --output-format json` returns {result, session_id, ...}
        text = data.get("result") or data.get("text") or raw
        new_session = data.get("session_id", session_id)
        return AgentReply(text=text, session_id=new_session)
    except json.JSONDecodeError:
        return AgentReply(text=raw, session_id=session_id)


async def _run_sdk(
    user_message: str, mode: str, session_id: str | None, context: dict | None = None
) -> AgentReply:
    try:
        from claude_agent_sdk import query  # type: ignore
    except ImportError:
        return AgentReply(
            text="(agent error) AGENT_MODE=sdk but claude-agent-sdk is not installed.",
            session_id=session_id,
        )
    system_prompt = prompts.for_mode(mode, context)
    chunks: list[str] = []
    async for message in query(prompt=user_message, options={"system_prompt": system_prompt}):
        text = getattr(message, "text", None)
        if text:
            chunks.append(text)
    return AgentReply(text="".join(chunks) or "(no reply)", session_id=session_id)


async def ask(
    user_message: str,
    mode: str,
    session_id: str | None = None,
    mcp_config_path: str | None = None,
    context: dict | None = None,
) -> AgentReply:
    """Run one fuzzy turn through the agent and return its reply."""
    if settings.agent_mode == "sdk":
        return await _run_sdk(user_message, mode, session_id, context)
    return await _run_cli(user_message, mode, session_id, mcp_config_path, context)
