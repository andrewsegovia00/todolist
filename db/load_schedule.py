"""Ingest the weekly schedule template into schedule_blocks (handoff Phase 3).

Reads db/schedule_template.json (copy from the .example), upserts each block.
Recurring blocks store their weekday spec in `recurring_rule`; the scheduler
projects the stored time-of-day onto matching days. One-off blocks store a
concrete date.

Run:  python -m db.load_schedule  [path/to/template.json]
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, time
from pathlib import Path

from core.logging_config import get_logger
from db.repos import schedule_repo

log = get_logger("db.load_schedule")

# Recurring blocks anchor their time-of-day on an arbitrary reference date; only
# the time portion matters for recurrence (the scheduler reprojects onto today).
_ANCHOR = date(2000, 1, 3)  # a Monday


def _parse_time(hhmm: str) -> time:
    hh, mm = hhmm.split(":")
    return time(int(hh), int(mm))


def _to_block(entry: dict) -> dict:
    start_t = _parse_time(entry["start"])
    end_t = _parse_time(entry["end"])
    if "days" in entry and entry["days"]:
        rule = entry["days"].strip().lower()
        anchor = _ANCHOR
    elif "date" in entry and entry["date"]:
        rule = None
        anchor = date.fromisoformat(entry["date"])
    else:
        raise ValueError(f"Block '{entry.get('label')}' needs either `days` or `date`.")
    return {
        "label": entry["label"],
        "category": entry.get("category"),
        "goal": entry.get("goal") or None,
        "start_at": datetime.combine(anchor, start_t).isoformat(),
        "end_at": datetime.combine(anchor, end_t).isoformat(),
        "recurring_rule": rule,
    }


def load(path: Path) -> int:
    data = json.loads(path.read_text())
    blocks = data.get("blocks", data if isinstance(data, list) else [])
    count = 0
    for entry in blocks:
        if entry.get("_comment"):
            continue
        b = _to_block(entry)
        schedule_repo.add_block(**b)
        count += 1
        log.info("Loaded block: %s (%s)", b["label"], b["recurring_rule"] or "one-off")
    return count


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    path = Path(arg) if arg else Path(__file__).parent / "schedule_template.json"
    if not path.exists():
        print(f"No template at {path}. Copy db/schedule_template.example.json and edit it.")
        return 1
    n = load(path)
    print(f"Loaded {n} schedule block(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
