"""Admin dashboard (handoff 5.7) — "command console" theme.

Server-rendered Flask running on the trusted hub; the browser never receives a
Supabase key (the server holds service_role). The manage page is registry-driven
(see dashboard/entities.py): list / filter / bulk-delete / bulk-retag / CSV
export / CSV import across every managed table.

Run:  python -m dashboard.app
"""
from __future__ import annotations

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from core.guardrails import run_all as run_guardrails
from core.settings import settings
from dashboard import csv_io, entities
from db.client import db
from db.repos import bulk_repo, config_repo, ideas_repo


def _count(table: str, **eq) -> int:
    q = db().table(table).select("id", count="exact").limit(1)
    for k, v in eq.items():
        q = q.eq(k, v)
    res = q.execute()
    return res.count or 0


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = settings.dashboard_secret or "dev-only-not-secret"

    @app.context_processor
    def inject_nav():
        return {"nav_entities": entities.all_entities()}

    # --- Home overview ------------------------------------------------------

    @app.route("/")
    def index():
        stats = [
            {"label": "Ideas", "value": _count("ideas"), "icon": "bulb", "key": "ideas"},
            {"label": "Open tasks", "value": _count("dead_time_tasks", state="open"),
             "icon": "checklist", "key": "tasks"},
            {"label": "Schedule blocks", "value": _count("schedule_blocks"),
             "icon": "calendar", "key": "schedule"},
            {"label": "Active projects", "value": _count("projects", active=True),
             "icon": "folder", "key": "projects"},
            {"label": "Buckets", "value": _count("buckets"), "icon": "bucket", "key": "buckets"},
            {"label": "Tags", "value": _count("tags"), "icon": "tag", "key": "tags"},
        ]
        return render_template("home.html", stats=stats)

    # --- Manage (registry-driven) ------------------------------------------

    @app.route("/manage/<entity_key>")
    def manage(entity_key: str):
        entity = entities.get(entity_key)
        if not entity:
            abort(404)
        args = {f.name: (request.args.get(f.name) or "") for f in entity.filters}
        rows = entity.rows(args)
        filters = [
            {"name": f.name, "label": f.label, "options": f.options(), "value": args.get(f.name, "")}
            for f in entity.filters
        ]
        return render_template(
            "manage.html",
            entity=entity,
            rows=rows,
            filters=filters,
            tags=config_repo.list_tags() if entity.supports_tags else [],
        )

    @app.route("/manage/<entity_key>/bulk-delete", methods=["POST"])
    def bulk_delete(entity_key: str):
        entity = entities.get(entity_key)
        if not entity or not entity.deletable:
            abort(404)
        ids = request.form.getlist("ids")
        if not ids:
            flash("Nothing selected.", "warn")
            return redirect(url_for("manage", entity_key=entity_key))
        n = bulk_repo.delete_many(entity.table, ids)
        flash(f"Deleted {n} {entity.label.lower()}.", "ok")
        return redirect(url_for("manage", entity_key=entity_key))

    @app.route("/manage/<entity_key>/bulk-tag", methods=["POST"])
    def bulk_tag(entity_key: str):
        entity = entities.get(entity_key)
        if not entity or not entity.supports_tags:
            abort(404)
        ids = request.form.getlist("ids")
        tag_id = request.form.get("tag_id") or None
        action = request.form.get("action", "add")
        if not ids or not tag_id:
            flash("Pick a tag and at least one row.", "warn")
            return redirect(url_for("manage", entity_key=entity_key))
        for idea_id in ids:
            if action == "remove":
                ideas_repo.remove_tag(idea_id, tag_id)
            else:
                ideas_repo.add_tag(idea_id, tag_id)
        verb = "Removed tag from" if action == "remove" else "Tagged"
        flash(f"{verb} {len(ids)} idea(s).", "ok")
        return redirect(url_for("manage", entity_key=entity_key))

    @app.route("/manage/<entity_key>/toggle-active", methods=["POST"])
    def toggle_active(entity_key: str):
        entity = entities.get(entity_key)
        if not entity or not entity.has_active:
            abort(404)
        row_id = request.form.get("id")
        desired = (request.form.get("active") == "true")
        if row_id:
            db().table(entity.table).update({"active": desired}).eq("id", row_id).execute()
            flash(("Restored" if desired else "Archived") + " 1 row.", "ok")
        return redirect(request.referrer or url_for("manage", entity_key=entity_key))

    @app.route("/manage/<entity_key>/add", methods=["POST"])
    def quick_add(entity_key: str):
        entity = entities.get(entity_key)
        if not entity or not entity.importable or not entity.create_fn:
            abort(404)
        rec: dict = {}
        for f in entity.import_fields:
            raw = (request.form.get(f.name) or "").strip()
            if not raw:
                continue
            rec[f.name] = f.coerce(raw) if f.coerce else raw
        missing = [f for f in entity.required_fields if not rec.get(f)]
        if missing:
            flash(f"Missing: {', '.join(missing)}.", "warn")
            return redirect(url_for("manage", entity_key=entity_key))
        entity.create_fn(rec)
        flash(f"Added 1 {entity.label.lower().rstrip('s')}.", "ok")
        return redirect(url_for("manage", entity_key=entity_key))

    @app.route("/manage/<entity_key>/export.csv")
    def export_csv(entity_key: str):
        entity = entities.get(entity_key)
        if not entity:
            abort(404)
        args = {f.name: (request.args.get(f.name) or "") for f in entity.filters}
        rows = entity.rows(args)
        ids_param = request.args.get("ids")
        if ids_param:
            wanted = set(ids_param.split(","))
            rows = [r for r in rows if str(r.get("id")) in wanted]
        flat = [entity.to_export_row(r) for r in rows]
        body = csv_io.to_csv(flat, entity.export_columns())
        return Response(
            body,
            mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{entity.key}.csv"'},
        )

    @app.route("/manage/<entity_key>/import", methods=["POST"])
    def import_csv(entity_key: str):
        entity = entities.get(entity_key)
        if not entity or not entity.importable or not entity.create_fn:
            abort(404)
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Choose a CSV file first.", "warn")
            return redirect(url_for("manage", entity_key=entity_key))
        text = file.read().decode("utf-8-sig", errors="replace")
        rows, errors = csv_io.parse_csv(
            text, entity.known_fields, entity.required_fields, entity.coercers
        )
        created = 0
        for rec in rows:
            try:
                entity.create_fn(rec)
                created += 1
            except Exception as e:  # surface, don't abort the batch
                errors.append(f"insert failed: {e}")
        msg = f"{created} created"
        if errors:
            shown = "; ".join(errors[:5])
            more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
            msg += f", {len(errors)} skipped: {shown}{more}"
        flash(msg, "ok" if created and not errors else ("warn" if created else "err"))
        return redirect(url_for("manage", entity_key=entity_key))

    # --- Single-idea editor (kept from the original dashboard) --------------

    @app.route("/ideas/<idea_id>/edit", methods=["GET", "POST"])
    def edit_idea(idea_id: str):
        idea = ideas_repo.get_idea(idea_id)
        if not idea:
            abort(404)
        if request.method == "POST":
            ideas_repo.update_idea(
                idea_id,
                title=request.form["title"].strip(),
                notes=request.form.get("notes", "").strip(),
                bucket_id=request.form.get("bucket_id") or None,
                project_id=request.form.get("project_id") or None,
                status_id=request.form.get("status_id") or None,
            )
            flash("Idea updated.", "ok")
            return redirect(url_for("manage", entity_key="ideas"))
        return render_template(
            "edit_idea.html",
            idea=idea,
            buckets=config_repo.list_buckets(active_only=False),
            projects=config_repo.list_projects(active_only=False),
            statuses=config_repo.list_statuses(active_only=False),
        )

    return app


def main() -> None:
    run_guardrails()
    app = create_app()
    app.run(host=settings.dashboard_host, port=settings.dashboard_port, debug=False)


if __name__ == "__main__":
    main()
