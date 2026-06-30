"""Pure-logic tests for the #ideas hybrid flow helpers (no network)."""
from __future__ import annotations

from bot.services import ideas_flow


def test_extract_json_plain():
    assert ideas_flow.extract_json('{"intent": "capture", "title": "Deck box"}') == {
        "intent": "capture",
        "title": "Deck box",
    }


def test_extract_json_with_code_fence():
    raw = '```json\n{"intent": "recall", "bucket": "The Shop"}\n```'
    assert ideas_flow.extract_json(raw) == {"intent": "recall", "bucket": "The Shop"}


def test_extract_json_with_surrounding_prose():
    raw = 'Here you go:\n{"intent": "capture", "items": ["a", "b"]}\nHope that helps!'
    assert ideas_flow.extract_json(raw) == {"intent": "capture", "items": ["a", "b"]}


def test_extract_json_garbage_returns_none():
    assert ideas_flow.extract_json("not json at all") is None
    assert ideas_flow.extract_json("") is None


def test_provisional_title_first_line_and_truncation():
    assert ideas_flow._provisional_title("Deck box idea\nmore detail") == "Deck box idea"
    long = "x" * 100
    out = ideas_flow._provisional_title(long)
    assert len(out) == 70 and out.endswith("…")
