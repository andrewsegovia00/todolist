"""Test fixtures: an in-memory fake of the Supabase client.

This lets the deterministic business logic (repos, timecard state machine,
dead-time matching) be tested without a live Supabase. It implements the subset
of the PostgREST query builder the repos actually use: select/insert/update/
delete/upsert with eq/in_/gte/lte/ilike filters, order, and limit.

Resource embedding (e.g. "*, bucket:buckets(id,name)") is parsed down to the base
columns — embeds resolve to None — which is enough for the logic under test.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from itertools import count

import pytest


# Server-side defaults that Postgres applies on insert (mirrors migration 0001).
_DEFAULTS: dict[str, dict] = {
    "buckets": {"active": True},
    "projects": {"active": True},
    "statuses": {"active": True},
    "schedule_blocks": {"active": True},
    "dead_time_tasks": {"state": "open", "priority": 0},
    "block_logs": {"state": "open"},
    "integrations": {"active": False},
}


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store: "_Store", table: str):
        self.store = store
        self.table = table
        self._op = "select"
        self._payload = None
        self._on_conflict = None
        self._filters: list = []
        self._orders: list[tuple[str, bool]] = []
        self._limit: int | None = None

    # --- op builders --------------------------------------------------------
    def select(self, _cols="*"):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self._op = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def delete(self):
        self._op = "delete"
        return self

    # --- filters ------------------------------------------------------------
    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, list(vals)))
        return self

    def gte(self, col, val):
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col, val):
        self._filters.append(("lte", col, val))
        return self

    def ilike(self, col, pattern):
        self._filters.append(("ilike", col, pattern))
        return self

    def order(self, col, desc=False):
        self._orders.append((col, desc))
        return self

    def limit(self, n):
        self._limit = n
        return self

    # --- execution ----------------------------------------------------------
    def _matches(self, row) -> bool:
        for kind, col, val in self._filters:
            cur = row.get(col)
            if kind == "eq" and cur != val:
                return False
            if kind == "in" and cur not in val:
                return False
            if kind == "gte" and not (cur is not None and cur >= val):
                return False
            if kind == "lte" and not (cur is not None and cur <= val):
                return False
            if kind == "ilike":
                regex = "^" + re.escape(val).replace("%", ".*") + "$"
                if cur is None or not re.match(regex, str(cur), re.IGNORECASE):
                    return False
        return True

    def execute(self):
        rows = self.store.tables.setdefault(self.table, [])

        if self._op == "insert":
            created = self._insert_rows(self._payload)
            return _Result([dict(r) for r in created])

        if self._op == "upsert":
            created = self._upsert_rows(self._payload)
            return _Result([dict(r) for r in created])

        if self._op == "update":
            changed = []
            for row in rows:
                if self._matches(row):
                    row.update(self._payload)
                    changed.append(dict(row))
            return _Result(changed)

        if self._op == "delete":
            keep, removed = [], []
            for row in rows:
                (removed if self._matches(row) else keep).append(row)
            self.store.tables[self.table] = keep
            return _Result([dict(r) for r in removed])

        # select
        out = [dict(r) for r in rows if self._matches(r)]
        for col, desc in reversed(self._orders):  # first .order() is primary
            out.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        if self._limit is not None:
            out = out[: self._limit]
        return _Result(out)

    # --- helpers ------------------------------------------------------------
    def _new_row(self, payload: dict) -> dict:
        row = dict(payload)
        # Apply the server-side column defaults real Postgres would fill in.
        for col, default in _DEFAULTS.get(self.table, {}).items():
            row.setdefault(col, default)
        row.setdefault("id", str(uuid.uuid4()))
        # monotonic created_at so ordering is deterministic in tests
        seq = next(self.store.seq)
        row.setdefault(
            "created_at",
            datetime.now(timezone.utc).isoformat() + f"{seq:09d}",
        )
        return row

    def _insert_rows(self, payload):
        rows = self.store.tables.setdefault(self.table, [])
        items = payload if isinstance(payload, list) else [payload]
        created = []
        for item in items:
            row = self._new_row(item)
            rows.append(row)
            created.append(row)
        return created

    def _upsert_rows(self, payload):
        rows = self.store.tables.setdefault(self.table, [])
        items = payload if isinstance(payload, list) else [payload]
        keys = [k.strip() for k in (self._on_conflict or "id").split(",")]
        created = []
        for item in items:
            existing = next(
                (r for r in rows if all(r.get(k) == item.get(k) for k in keys)), None
            )
            if existing:
                existing.update(item)
                created.append(existing)
            else:
                row = self._new_row(item)
                rows.append(row)
                created.append(row)
        return created


class _Store:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}
        self.seq = count(1)

    def table(self, name):
        return _Query(self, name)

    # convenience for seeding in tests
    def insert(self, table, **row):
        return self.table(table).insert(row).execute().data[0]


@pytest.fixture
def fake_db(monkeypatch):
    """Patch the repos' db handle to an in-memory store and seed base config."""
    store = _Store()
    # repos call db.client.db() -> get_service_client(); patch the latter.
    monkeypatch.setattr("db.client.get_service_client", lambda: store, raising=True)

    # Seed the static pipeline so status-dependent logic works.
    for i, name in enumerate(
        ["Idea", "Developing", "Scripted", "Producing", "Editing", "Scheduled", "Published"],
        start=1,
    ):
        store.insert("statuses", name=name, sort_order=i, active=True)
    return store
