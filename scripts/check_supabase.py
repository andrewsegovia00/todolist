"""Phase-0 check: verify Supabase connectivity by reading active buckets.

Run:  python -m scripts.check_supabase
"""
from __future__ import annotations

import sys

from db.repos import config_repo


def main() -> int:
    try:
        buckets = config_repo.list_buckets()
    except Exception as e:  # noqa: BLE001
        print(f"❌ Supabase read failed: {e}")
        print("   Check SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY and that migrations ran.")
        return 1
    names = ", ".join(b["name"] for b in buckets) or "(none — did you run migrations + seed?)"
    print(f"✅ Supabase reachable. Active buckets: {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
