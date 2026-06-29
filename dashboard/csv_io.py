"""Pure CSV helpers for the manage page (export + import).

Deliberately decoupled from the database and from Flask so the logic is
unit-testable with no network (matches the existing `tests/` convention):

  - `to_csv(rows, columns)` renders already-flattened rows to a CSV string.
  - `parse_csv(text, known_fields, ...)` parses an uploaded CSV into validated
    field dicts plus a list of human-readable per-row errors.

Coercion and required-field rules are passed in by the caller (the entity
registry), keeping this module generic.
"""
from __future__ import annotations

import csv
import io
from typing import Callable

# A column is (field_key, header_label).
Column = tuple[str, str]


def to_csv(rows: list[dict], columns: list[Column]) -> str:
    """Render rows to a CSV string using `columns` for header + ordering.

    Each row is expected to already hold primitive, display-ready values under
    the column keys (the entity registry flattens nested objects first).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([label for _key, label in columns])
    for row in rows:
        writer.writerow([_stringify(row.get(key, "")) for key, _label in columns])
    return buf.getvalue()


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def parse_csv(
    text: str,
    known_fields: list[str],
    required_fields: tuple[str, ...] = (),
    coercers: dict[str, Callable[[str], object]] | None = None,
) -> tuple[list[dict], list[str]]:
    """Parse CSV text into (valid_rows, errors).

    - Columns not in `known_fields` are ignored.
    - A row missing any `required_fields` (empty/absent) is skipped with an
      error; other rows still parse.
    - `coercers[field]` converts a cell string; a raised exception turns into a
      per-row error and the row is skipped.
    - Header matching is case-insensitive and trims whitespace.
    """
    coercers = coercers or {}
    rows: list[dict] = []
    errors: list[str] = []

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], ["CSV is empty (no header row)."]

    # Map column index -> known field name (case-insensitive).
    field_by_index: dict[int, str] = {}
    known_lower = {f.lower(): f for f in known_fields}
    for idx, col in enumerate(header):
        key = col.strip().lower()
        if key in known_lower:
            field_by_index[idx] = known_lower[key]

    if not field_by_index:
        return [], [
            "No recognizable columns. Expected one of: " + ", ".join(known_fields) + "."
        ]

    for line_no, raw in enumerate(reader, start=2):  # row 1 is the header
        if not any(cell.strip() for cell in raw):
            continue  # skip blank lines
        record: dict[str, object] = {}
        row_error: str | None = None
        for idx, field in field_by_index.items():
            value = raw[idx].strip() if idx < len(raw) else ""
            if value == "":
                continue
            if field in coercers:
                try:
                    record[field] = coercers[field](value)
                except (ValueError, TypeError):
                    row_error = f"row {line_no}: invalid value for '{field}': {value!r}"
                    break
            else:
                record[field] = value
        if row_error:
            errors.append(row_error)
            continue

        missing = [f for f in required_fields if not record.get(f)]
        if missing:
            errors.append(f"row {line_no}: missing required field(s): {', '.join(missing)}")
            continue

        rows.append(record)

    return rows, errors
