import json
from datetime import datetime

import pytest

from db import load_schedule
from db.repos import schedule_repo


def test_recurring_block_keeps_time_and_rule():
    b = load_schedule._to_block(
        {"label": "Lift", "days": "mon,wed,fri", "start": "06:00", "end": "07:00"}
    )
    assert b["recurring_rule"] == "mon,wed,fri"
    assert datetime.fromisoformat(b["start_at"]).time().hour == 6
    assert datetime.fromisoformat(b["end_at"]).time().hour == 7


def test_one_off_block_uses_date_and_no_rule():
    b = load_schedule._to_block(
        {"label": "Dentist", "date": "2026-07-02", "start": "14:00", "end": "15:00"}
    )
    assert b["recurring_rule"] is None
    assert datetime.fromisoformat(b["start_at"]).date().isoformat() == "2026-07-02"


def test_block_without_days_or_date_raises():
    with pytest.raises(ValueError):
        load_schedule._to_block({"label": "Bad", "start": "09:00", "end": "10:00"})


def test_load_persists_blocks(fake_db, tmp_path):
    template = {
        "blocks": [
            {"_comment": "skip me"},
            {"label": "A", "days": "daily", "start": "08:00", "end": "09:00"},
            {"label": "B", "date": "2026-07-01", "start": "10:00", "end": "11:00"},
        ]
    }
    path = tmp_path / "schedule_template.json"
    path.write_text(json.dumps(template))

    n = load_schedule.load(path)
    assert n == 2
    labels = {b["label"] for b in schedule_repo.list_blocks()}
    assert labels == {"A", "B"}
