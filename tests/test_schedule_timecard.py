from datetime import date

from db.repos import schedule_repo


def _block(fake_db):
    return fake_db.insert("schedule_blocks", label="Lift", category="Fitness", active=True)


def test_ensure_log_is_idempotent_per_day(fake_db):
    b = _block(fake_db)
    on = date(2026, 6, 19)
    a = schedule_repo.ensure_log(b["id"], on)
    again = schedule_repo.ensure_log(b["id"], on)
    assert a["id"] == again["id"]
    assert a["state"] == "open"


def test_close_log_records_completion(fake_db):
    b = _block(fake_db)
    on = date(2026, 6, 19)
    row = schedule_repo.close_log(b["id"], on, completed=True)
    assert row["state"] == "closed"
    assert row["completed"] is True
    assert row["finish_time"] is not None


def test_mark_unclosed_does_not_override_closed(fake_db):
    b = _block(fake_db)
    on = date(2026, 6, 19)
    schedule_repo.close_log(b["id"], on, completed=False)
    row = schedule_repo.mark_unclosed(b["id"], on)
    assert row["state"] == "closed"  # stays closed, not downgraded


def test_mark_unclosed_promotes_open(fake_db):
    b = _block(fake_db)
    on = date(2026, 6, 19)
    schedule_repo.ensure_log(b["id"], on)
    row = schedule_repo.mark_unclosed(b["id"], on)
    assert row["state"] == "unclosed"


def test_exclude_log_marks_excluded(fake_db):
    b = _block(fake_db)
    on = date(2026, 6, 19)
    row = schedule_repo.exclude_log(b["id"], on)
    assert row["state"] == "excluded"
