from datetime import datetime
from zoneinfo import ZoneInfo

from bot.scheduler import _parse_dt, _same_minute

TZ = ZoneInfo("America/Phoenix")


def test_same_minute_ignores_seconds():
    a = datetime(2026, 6, 19, 14, 30, 5, tzinfo=TZ)
    b = datetime(2026, 6, 19, 14, 30, 59, tzinfo=TZ)
    assert _same_minute(a, b)


def test_same_minute_distinguishes_minutes():
    a = datetime(2026, 6, 19, 14, 30, tzinfo=TZ)
    b = datetime(2026, 6, 19, 14, 31, tzinfo=TZ)
    assert not _same_minute(a, b)


def test_parse_dt_assigns_tz_when_naive():
    dt = _parse_dt("2026-06-19T14:30:00", TZ)
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_dt_handles_z_suffix():
    dt = _parse_dt("2026-06-19T21:30:00Z", TZ)
    assert dt is not None
    # 21:30 UTC -> 14:30 MST (Phoenix, UTC-7)
    assert dt.hour == 14
