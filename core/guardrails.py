"""Startup guardrails — fail loudly when a hard constraint is violated.

The single most important rule (handoff Section 1.1): the agent runs through
Claude Code authenticated to the Max subscription, NEVER a billed API key. If
ANTHROPIC_API_KEY is set in the environment, Claude Code silently bills the API.
We refuse to start in that case.
"""
from __future__ import annotations

import os


class GuardrailError(RuntimeError):
    """Raised when a hard constraint is violated at startup."""


def assert_no_anthropic_api_key() -> None:
    """Fail loudly if ANTHROPIC_API_KEY (or its alias) is present.

    Keeps the $0-extra-cost guarantee: subscription auth only.
    """
    offenders = [
        name
        for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
        if os.environ.get(name)
    ]
    if offenders:
        raise GuardrailError(
            "Refusing to start: "
            + ", ".join(offenders)
            + " is set. This would make Claude Code bill the API instead of "
            "using the Max subscription. Unset it (it must NOT be in the bot's "
            "environment) and restart. See handoff Section 1, guardrail #1."
        )


def run_all() -> None:
    """Run every startup guardrail. Call before bringing any surface online."""
    assert_no_anthropic_api_key()
