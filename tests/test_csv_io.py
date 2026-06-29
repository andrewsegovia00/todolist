"""Pure-logic tests for dashboard.csv_io (no network)."""
from __future__ import annotations

from dashboard import csv_io


def test_to_csv_header_and_order():
    rows = [{"title": "A", "bucket": "Shop"}, {"title": "B", "bucket": None}]
    out = csv_io.to_csv(rows, [("title", "Title"), ("bucket", "Bucket")])
    lines = out.strip().splitlines()
    assert lines[0] == "Title,Bucket"
    assert lines[1] == "A,Shop"
    assert lines[2] == "B,"  # None renders as empty


def test_to_csv_booleans():
    out = csv_io.to_csv([{"active": True}, {"active": False}], [("active", "Active")])
    assert out.strip().splitlines()[1:] == ["true", "false"]


def test_parse_csv_roundtrip():
    columns = [("title", "Title"), ("bucket", "Bucket")]
    rows = [{"title": "A", "bucket": "Shop"}, {"title": "B", "bucket": "Market"}]
    text = csv_io.to_csv(rows, columns)
    parsed, errors = csv_io.parse_csv(text, ["title", "bucket"], required_fields=("title",))
    assert errors == []
    assert parsed == rows


def test_parse_csv_ignores_unknown_columns():
    text = "Title,Extra\nHello,junk\n"
    parsed, errors = csv_io.parse_csv(text, ["title"], required_fields=("title",))
    assert parsed == [{"title": "Hello"}]
    assert errors == []


def test_parse_csv_missing_required():
    text = "title,notes\n,note-only\nReal,ok\n"
    parsed, errors = csv_io.parse_csv(text, ["title", "notes"], required_fields=("title",))
    assert parsed == [{"title": "Real", "notes": "ok"}]
    assert len(errors) == 1 and "row 2" in errors[0]


def test_parse_csv_coercion_good_and_bad():
    text = "content,priority\nfoo,3\nbar,high\n"
    parsed, errors = csv_io.parse_csv(
        text, ["content", "priority"], required_fields=("content",), coercers={"priority": int}
    )
    assert parsed == [{"content": "foo", "priority": 3}]
    assert len(errors) == 1 and "priority" in errors[0]


def test_parse_csv_case_insensitive_headers_and_blank_lines():
    text = "TITLE\nA\n\n   \nB\n"
    parsed, errors = csv_io.parse_csv(text, ["title"], required_fields=("title",))
    assert parsed == [{"title": "A"}, {"title": "B"}]
    assert errors == []


def test_parse_csv_empty_and_unrecognized():
    assert csv_io.parse_csv("", ["title"])[1]  # empty -> error
    rows, errors = csv_io.parse_csv("nope,zip\n1,2\n", ["title"])
    assert rows == [] and errors  # no recognizable columns
