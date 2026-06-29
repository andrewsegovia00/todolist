"""Generic bulk operations used by the dashboard manage page.

Kept tiny and table-agnostic: every managed table has a single-column primary
key named `id` (the one exception, `channel_config`, is not bulk-managed here).
"""
from __future__ import annotations

from db.client import db


def delete_many(table: str, ids: list[str]) -> int:
    """Delete rows whose `id` is in `ids`. Returns the number requested."""
    ids = [i for i in ids if i]
    if not ids:
        return 0
    db().table(table).delete().in_("id", ids).execute()
    return len(ids)
