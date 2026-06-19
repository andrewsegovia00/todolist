"""Phase-0 guard: assert ANTHROPIC_API_KEY is unset and report config presence.

Run:  python -m scripts.check_env
"""
from __future__ import annotations

import sys

from core.guardrails import GuardrailError, assert_no_anthropic_api_key
from core.settings import settings


def main() -> int:
    ok = True

    # Hard guardrail.
    try:
        assert_no_anthropic_api_key()
        print("✅ ANTHROPIC_API_KEY is unset (subscription auth preserved).")
    except GuardrailError as e:
        print(f"❌ {e}")
        ok = False

    # Presence report (not all are required at every phase).
    checks = {
        "DISCORD_BOT_TOKEN": settings.discord_bot_token,
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
        "SUPABASE_ANON_KEY": settings.supabase_anon_key,
        "OWNER_DISCORD_USER_ID": settings.owner_discord_user_id,
        "PARTNER_DISCORD_USER_ID": settings.partner_discord_user_id,
        "PARTNER_DISPLAY_NAME": settings.partner_display_name,
        "HUB_OS": settings.hub_os,
    }
    print("\nConfig presence:")
    for key, val in checks.items():
        print(f"  {'✅' if val else '⚠️ '} {key}{'' if val else ' (unset)'}")

    print(f"\nAgent mode: {settings.agent_mode}  ·  timezone: {settings.timezone}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
