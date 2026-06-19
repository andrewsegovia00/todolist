from datetime import date

from bot.services import analytics
from bot.services.analytics import WeeklyRecap


def test_week_bounds_is_monday_to_sunday():
    start, end = analytics.week_bounds(date(2026, 6, 17))  # a Wednesday
    assert start == date(2026, 6, 15)  # Monday
    assert end == date(2026, 6, 21)    # Sunday
    assert start.weekday() == 0
    assert end.weekday() == 6


def test_recap_metrics_exclude_dayoff():
    r = WeeklyRecap(start=date(2026, 6, 15), end=date(2026, 6, 21))
    r.total = 10
    r.completed = 6
    r.unclosed = 1
    r.open_blank = 1
    r.excluded = 2
    # counted excludes day-off instances
    assert r.counted == 8
    assert r.dead_spots == 2
    assert r.adherence_pct == 75.0  # 6 / 8


def test_adherence_none_when_all_excluded():
    r = WeeklyRecap(start=date(2026, 6, 15), end=date(2026, 6, 21))
    r.total = 3
    r.excluded = 3
    assert r.counted == 0
    assert r.adherence_pct is None
