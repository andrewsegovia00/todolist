# Manage page — design spec

Date: 2026-06-28
Status: approved (design); implementation pending

## Goal

Add a general-purpose admin "manage" page to the dashboard that lets the owner
view, filter, bulk-delete, bulk re-tag (ideas only), export to CSV, and import
from CSV across all the meaningful tables in the Command Hub database — not just
ideas.

This extends the existing Flask dashboard (server-rendered on the trusted hub,
holds the Supabase `service_role` key). It respects guardrail #4: functional and
neutral styling only, no imposed visual design.

## Approach (chosen: registry-driven generic browser)

One page works over a registry of "manageable entities." The list view,
row checkboxes, bulk-delete, CSV export, and CSV import are written once and
driven by per-entity config. Adding a new table later is a single registry entry.

The existing Ideas page is folded in as one entity so all management is
consistent.

## Entities (v1 registry)

| Entity            | Table             | Filters                     | Bulk delete | Export CSV | Import CSV | Re-tag |
|-------------------|-------------------|-----------------------------|-------------|------------|------------|--------|
| Ideas             | `ideas`           | bucket/project/status/tag   | yes         | yes        | yes        | yes    |
| Dead-time tasks   | `dead_time_tasks` | state                       | yes         | yes        | yes        | no     |
| Schedule blocks   | `schedule_blocks` | active                      | yes         | yes        | yes        | no     |
| Day-offs          | `day_off`         | —                           | yes         | yes        | yes        | no     |
| Projects          | `projects`        | active                      | yes         | yes        | yes        | no     |
| Buckets           | `buckets`         | active                      | yes         | yes        | yes        | no     |
| Tags              | `tags`            | —                           | yes         | yes        | yes        | no     |
| Statuses          | `statuses`        | —                           | yes         | yes        | yes        | no     |
| Events (audit)    | `events`          | —                           | no          | yes (export-only) | no | no     |

Excluded from v1 (structural/sensitive; easy to add later): `people`,
`settings`, `channel_config`, `integrations`, `idea_tags`.

Re-tag is ideas-only because tags are an ideas-only concept (`idea_tags`).

## UX

- New route group at `/manage`, with a tab/nav row to switch entity.
- Each entity view: filter bar (where the entity declares filters) → table with a
  checkbox per row + "select all" → a bulk-action toolbar:
  - `Delete selected` (danger) — opens the existing confirm modal showing the
    count.
  - `Export CSV` — exports the checked rows; if nothing is checked, exports the
    whole filtered set.
  - `Tag selected ▾` (ideas only) — pick a tag + Add or Remove, applied to the
    checked rows.
  - `Import CSV` — file picker + submit; on success flashes a summary
    ("12 created, 2 skipped: row 4 missing title").
- Styling stays neutral: extend `dashboard/static/style.css`, no redesign.

## Modules (isolation)

- `dashboard/entities.py` — the registry. An `Entity` spec (dataclass) per table:
  `key`, `label`, `table`, `list_fn`, `columns` (list of `(field, label)`),
  `filters` (declarative), `importable_fields`, `supports_tags`. Pure config
  wired to existing `db/repos/*` where a repo exists; otherwise a thin generic
  list via `db()`.
- `dashboard/csv_io.py` — pure functions:
  - `to_csv(rows, columns) -> str`
  - `parse_csv(text, fields) -> (valid_rows, errors)`
  Fully unit-tested, no network.
- `db/repos/bulk_repo.py` — generic `delete_many(table, ids) -> int` via
  `db().table(table).delete().in_("id", ids)`.
- `dashboard/app.py` — new `/manage/...` routes driven by the registry.
- `dashboard/templates/manage.html` — one generic template for all entities:
  tab nav, filter bar, checkbox table, bulk toolbar, import form, reused delete
  modal.

## Routes

```
GET  /manage                      -> redirect to first entity
GET  /manage/<entity>             -> filtered list + checkboxes + toolbar
POST /manage/<entity>/bulk-delete -> delete checked ids (after confirm)
POST /manage/<entity>/bulk-tag    -> ideas only: add/remove a tag on checked ids
GET  /manage/<entity>/export.csv  -> CSV of checked ids, else whole filtered set
POST /manage/<entity>/import      -> upload CSV -> create rows -> flash summary
```

Unknown `<entity>` -> 404.

## CSV import semantics

- Header row maps to the entity's `importable_fields`; unknown columns are
  ignored; a row missing a required field is skipped with a reason while other
  rows still import.
- Create-only in v1 (no update/upsert).
- For Ideas, `bucket` / `project` / `status` are accepted by name (resolved to
  ids); an optional `tags` column (comma-separated) is auto-created and linked.
- Numeric fields (e.g. `priority`, `duration_est_min`) are coerced; bad values
  produce a per-row error.
- Result is reported as a summary: N created, M skipped with row-level reasons.

## CSV export semantics

- Columns follow the entity's `columns` config (flattened display values, e.g.
  bucket name rather than bucket id for ideas).
- Scope: checked ids if any are selected, otherwise the current filtered set.
- `Content-Disposition: attachment; filename="<entity>.csv"`.

## Error handling & safety

- No selection on a bulk action -> flash "nothing selected", no-op.
- Bulk delete is gated behind the confirm modal.
- FK behavior is safe per the schema: `ideas.bucket_id` / `ideas.project_id` use
  `ON DELETE SET NULL`; `idea_tags`, `block_logs` cascade. Deleting a
  referenced bucket/project nulls the reference rather than failing.
- Malformed CSV -> flash error; per-row failures are collected and reported,
  never a half-applied batch beyond the rows that genuinely validated.

## Testing (pure logic, no network — matches existing `tests/`)

- `csv_io` round-trip: `rows -> to_csv -> parse_csv` is equivalent.
- `parse_csv` validation: missing required field, unknown columns ignored,
  numeric coercion (good and bad values).
- Registry integrity: every entity has the required spec keys; every
  `importable_field` is a known field for that entity.
- Name->id resolution helper for ideas import (tested with a fake resolver so no
  network is required).

## Out of scope (YAGNI)

- File attachments / Supabase Storage.
- JSON export.
- Inline cell editing.
- Update-via-import (upsert).
- Auth changes (dashboard is already hub-trusted + optional `DASHBOARD_SECRET`).

## Notes

- Dashboard uses the `service_role` client (`db()`), so RLS does not block these
  admin operations.
- Pagination: list views keep a reasonable row limit (reuse the existing
  `limit=100` default); if a table grows large, add pagination later.
