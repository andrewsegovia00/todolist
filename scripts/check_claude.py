"""Phase-0 check: verify the subscription-authed agent responds.

Runs a trivial `claude -p "ping"` (or the SDK path) with the API-key guardrail
enforced first. Run:  python -m scripts.check_claude
"""
from __future__ import annotations

import asyncio
import sys

from core.guardrails import GuardrailError, assert_no_anthropic_api_key
from agent import runner


async def _run() -> int:
    try:
        assert_no_anthropic_api_key()
    except GuardrailError as e:
        print(f"❌ {e}")
        return 1
    reply = await runner.ask("Reply with the single word: pong", mode="config")
    print(f"Agent replied: {reply.text!r}")
    if "pong" in reply.text.lower():
        print("✅ Subscription-authed agent is responding.")
        return 0
    print("⚠️  Got a reply but not the expected token — check Claude Code login on the hub.")
    return 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
