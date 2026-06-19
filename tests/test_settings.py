from datetime import time

from core.settings import _parse_hhmm


def test_parse_hhmm_valid():
    assert _parse_hhmm("07:30", time(0, 0)) == time(7, 30)


def test_parse_hhmm_falls_back_on_garbage():
    assert _parse_hhmm("nonsense", time(9, 0)) == time(9, 0)
    assert _parse_hhmm(None, time(9, 0)) == time(9, 0)
