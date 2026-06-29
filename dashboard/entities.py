"""Registry of manageable entities for the dashboard manage page.

One declarative spec per table drives the generic list view, CSV export, CSV
import, bulk delete, and (for ideas) bulk re-tag. Adding a new manageable table
is a single entry in ENTITIES.

Each entity reuses the existing `db/repos/*` where one fits and falls back to a
thin `db()` query otherwise.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable

from db.client import db
from db.repos import config_repo, deadtime_repo, events_repo, ideas_repo, schedule_repo


# --- Spec types -------------------------------------------------------------


@dataclass
class Column:
    key: str
    label: str
    get: Callable[[dict], object] | None = None

    def value(self, row: dict) -> object:
        return self.get(row) if self.get else row.get(self.key)


@dataclass
class Filter:
    name: str
    label: str
    options: Callable[[], list[str]]


@dataclass
class ImportField:
    name: str
    required: bool = False
    coerce: Callable[[str], object] | None = None
    help: str = ""


@dataclass
class Entity:
    key: str
    label: str
    icon: str
    table: str
    columns: list[Column]
    list_fn: Callable[[dict], list[dict]]
    filters: list[Filter] = field(default_factory=list)
    import_fields: list[ImportField] = field(default_factory=list)
    create_fn: Callable[[dict], dict] | None = None
    supports_tags: bool = False
    deletable: bool = True
    importable: bool = True

    def rows(self, args: dict | None = None) -> list[dict]:
        return self.list_fn(args or {})

    def export_columns(self) -> list[tuple[str, str]]:
        return [(c.key, c.label) for c in self.columns]

    def to_export_row(self, row: dict) -> dict:
        return {c.key: c.value(row) for c in self.columns}

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.import_fields if f.required)

    @property
    def known_fields(self) -> list[str]:
        return [f.name for f in self.import_fields]

    @property
    def coercers(self) -> dict[str, Callable[[str], object]]:
        return {f.name: f.coerce for f in self.import_fields if f.coerce}

    @property
    def has_active(self) -> bool:
        return any(c.key == "active" for c in self.columns)


# --- Helpers ----------------------------------------------------------------


def _int(v: str) -> int:
    return int(v)


def _nested(parent: str, key: str = "name") -> Callable[[dict], object]:
    return lambda r: (r.get(parent) or {}).get(key)


def _truthy(v: str | None) -> bool | None:
    if v is None or v == "":
        return None
    return v.lower() in ("1", "true", "yes", "on")


def _generic_insert(table: str) -> Callable[[dict], dict]:
    return lambda rec: db().table(table).insert(rec).execute().data[0]


# --- Per-entity list functions ----------------------------------------------


def _ideas_list(args: dict) -> list[dict]:
    bucket = args.get("bucket") or None
    project = args.get("project") or None
    status = args.get("status") or None
    tag = args.get("tag") or None
    b = config_repo.get_bucket_by_name(bucket) if bucket else None
    p = config_repo.get_project_by_name(project) if project else None
    s = config_repo.get_status_by_name(status) if status else None
    t = next((x for x in config_repo.list_tags() if x["name"] == tag), None) if tag else None
    return ideas_repo.list_ideas(
        bucket_id=b["id"] if b else None,
        project_id=p["id"] if p else None,
        status_id=s["id"] if s else None,
        tag_id=t["id"] if t else None,
        limit=500,
    )


def _tasks_list(args: dict) -> list[dict]:
    q = db().table("dead_time_tasks").select("*")
    state = args.get("state") or None
    if state:
        q = q.eq("state", state)
    return q.order("priority", desc=True).order("created_at").limit(500).execute().data


def _blocks_list(args: dict) -> list[dict]:
    q = db().table("schedule_blocks").select("*")
    active = _truthy(args.get("active"))
    if active is not None:
        q = q.eq("active", active)
    return q.order("start_at").limit(500).execute().data


def _dayoff_list(args: dict) -> list[dict]:
    return (
        db().table("day_off").select("*, person:people(name)").order("start_at").limit(500).execute().data
    )


def _projects_list(args: dict) -> list[dict]:
    q = db().table("projects").select("*")
    active = _truthy(args.get("active"))
    if active is not None:
        q = q.eq("active", active)
    return q.order("name").execute().data


def _buckets_list(args: dict) -> list[dict]:
    q = db().table("buckets").select("*")
    active = _truthy(args.get("active"))
    if active is not None:
        q = q.eq("active", active)
    return q.order("name").execute().data


def _tags_list(args: dict) -> list[dict]:
    return config_repo.list_tags()


def _statuses_list(args: dict) -> list[dict]:
    return config_repo.list_statuses(active_only=False)


def _events_list(args: dict) -> list[dict]:
    return events_repo.recent(500)


# --- Ideas import (name resolution + tags) ----------------------------------


def _create_idea(rec: dict) -> dict:
    b = config_repo.get_bucket_by_name(rec["bucket"]) if rec.get("bucket") else None
    p = config_repo.get_project_by_name(rec["project"]) if rec.get("project") else None
    s = config_repo.get_status_by_name(rec["status"]) if rec.get("status") else None
    idea = ideas_repo.create_idea(
        title=rec["title"],
        notes=rec.get("notes"),
        bucket_id=b["id"] if b else None,
        project_id=p["id"] if p else None,
        status_id=s["id"] if s else None,
    )
    tags = rec.get("tags")
    if tags:
        for name in [x.strip() for x in str(tags).split(",") if x.strip()]:
            tg = config_repo.get_or_create_tag(name)
            ideas_repo.add_tag(idea["id"], tg["id"])
    return idea


# --- Registry ---------------------------------------------------------------


def _names(list_fn: Callable[[], list[dict]]) -> Callable[[], list[str]]:
    return lambda: [r["name"] for r in list_fn()]


ENTITIES: "OrderedDict[str, Entity]" = OrderedDict()


def _register(entity: Entity) -> None:
    ENTITIES[entity.key] = entity


_register(
    Entity(
        key="ideas",
        label="Ideas",
        icon="bulb",
        table="ideas",
        columns=[
            Column("title", "Title"),
            Column("bucket", "Bucket", _nested("bucket")),
            Column("project", "Project", _nested("project")),
            Column("status", "Status", _nested("status")),
            Column("author", "Author", _nested("author")),
            Column("created_at", "Created"),
        ],
        list_fn=_ideas_list,
        filters=[
            Filter("bucket", "Bucket", _names(lambda: config_repo.list_buckets(active_only=False))),
            Filter("project", "Project", _names(lambda: config_repo.list_projects(active_only=False))),
            Filter("status", "Status", _names(lambda: config_repo.list_statuses(active_only=False))),
            Filter("tag", "Tag", _names(config_repo.list_tags)),
        ],
        import_fields=[
            ImportField("title", required=True),
            ImportField("notes"),
            ImportField("bucket", help="bucket name"),
            ImportField("project", help="project name"),
            ImportField("status", help="status name"),
            ImportField("tags", help="comma-separated"),
        ],
        create_fn=_create_idea,
        supports_tags=True,
    )
)

_register(
    Entity(
        key="tasks",
        label="Dead-time tasks",
        icon="checklist",
        table="dead_time_tasks",
        columns=[
            Column("content", "Task"),
            Column("priority", "Priority"),
            Column("category", "Category"),
            Column("duration_est_min", "Est. min"),
            Column("state", "State"),
            Column("created_at", "Created"),
        ],
        list_fn=_tasks_list,
        filters=[Filter("state", "State", lambda: ["open", "done"])],
        import_fields=[
            ImportField("content", required=True),
            ImportField("priority", coerce=_int),
            ImportField("category"),
            ImportField("duration_est_min", coerce=_int),
        ],
        create_fn=_generic_insert("dead_time_tasks"),
    )
)

_register(
    Entity(
        key="schedule",
        label="Schedule blocks",
        icon="calendar",
        table="schedule_blocks",
        columns=[
            Column("label", "Label"),
            Column("category", "Category"),
            Column("goal", "Goal"),
            Column("start_at", "Start"),
            Column("end_at", "End"),
            Column("recurring_rule", "Recurs"),
            Column("active", "Active"),
        ],
        list_fn=_blocks_list,
        filters=[Filter("active", "Active", lambda: ["true", "false"])],
        import_fields=[
            ImportField("label", required=True),
            ImportField("category"),
            ImportField("goal"),
            ImportField("start_at"),
            ImportField("end_at"),
            ImportField("recurring_rule", help="e.g. weekdays / mon,wed,fri"),
        ],
        create_fn=_generic_insert("schedule_blocks"),
    )
)

_register(
    Entity(
        key="dayoffs",
        label="Day-offs",
        icon="beach",
        table="day_off",
        columns=[
            Column("start_at", "Start"),
            Column("end_at", "End"),
            Column("reason", "Reason"),
            Column("person", "Person", _nested("person")),
        ],
        list_fn=_dayoff_list,
        import_fields=[
            ImportField("start_at", required=True),
            ImportField("end_at", required=True),
            ImportField("reason"),
        ],
        create_fn=_generic_insert("day_off"),
    )
)

_register(
    Entity(
        key="projects",
        label="Projects",
        icon="folder",
        table="projects",
        columns=[
            Column("name", "Name"),
            Column("description", "Description"),
            Column("active", "Active"),
            Column("created_at", "Created"),
        ],
        list_fn=_projects_list,
        filters=[Filter("active", "Active", lambda: ["true", "false"])],
        import_fields=[ImportField("name", required=True), ImportField("description")],
        create_fn=_generic_insert("projects"),
    )
)

_register(
    Entity(
        key="buckets",
        label="Buckets",
        icon="bucket",
        table="buckets",
        columns=[
            Column("name", "Name"),
            Column("description", "Description"),
            Column("active", "Active"),
            Column("created_at", "Created"),
        ],
        list_fn=_buckets_list,
        filters=[Filter("active", "Active", lambda: ["true", "false"])],
        import_fields=[ImportField("name", required=True), ImportField("description")],
        create_fn=_generic_insert("buckets"),
    )
)

_register(
    Entity(
        key="tags",
        label="Tags",
        icon="tag",
        table="tags",
        columns=[Column("name", "Name")],
        list_fn=_tags_list,
        import_fields=[ImportField("name", required=True)],
        create_fn=_generic_insert("tags"),
    )
)

_register(
    Entity(
        key="statuses",
        label="Statuses",
        icon="flag",
        table="statuses",
        columns=[
            Column("name", "Name"),
            Column("sort_order", "Order"),
            Column("active", "Active"),
        ],
        list_fn=_statuses_list,
        import_fields=[
            ImportField("name", required=True),
            ImportField("sort_order", coerce=_int),
        ],
        create_fn=_generic_insert("statuses"),
    )
)

_register(
    Entity(
        key="events",
        label="Events",
        icon="history",
        table="events",
        columns=[
            Column("type", "Type"),
            Column("actor", "Actor"),
            Column("payload", "Payload"),
            Column("created_at", "Created"),
        ],
        list_fn=_events_list,
        deletable=False,
        importable=False,
    )
)


def get(key: str) -> Entity | None:
    return ENTITIES.get(key)


def all_entities() -> list[Entity]:
    return list(ENTITIES.values())
