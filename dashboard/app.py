"""Admin dashboard (handoff 5.7).

Functional first, neutral styling (guardrail #4) — a clean component structure
the owner can restyle later. Server-rendered Flask running on the trusted hub;
the browser never receives a Supabase key (the server holds service_role).

Run:  python -m dashboard.app
"""
from __future__ import annotations

from flask import Flask, abort, flash, redirect, render_template, request, url_for

from core.guardrails import run_all as run_guardrails
from core.settings import settings
from db.repos import config_repo, ideas_repo


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = settings.dashboard_secret or "dev-only-not-secret"

    @app.route("/")
    def index():
        bucket = request.args.get("bucket") or None
        project = request.args.get("project") or None
        tag = request.args.get("tag") or None

        bucket_row = config_repo.get_bucket_by_name(bucket) if bucket else None
        project_row = config_repo.get_project_by_name(project) if project else None
        tag_rows = config_repo.list_tags()
        tag_row = next((t for t in tag_rows if t["name"] == tag), None) if tag else None

        ideas = ideas_repo.list_ideas(
            bucket_id=bucket_row["id"] if bucket_row else None,
            project_id=project_row["id"] if project_row else None,
            tag_id=tag_row["id"] if tag_row else None,
        )
        return render_template(
            "index.html",
            ideas=ideas,
            buckets=config_repo.list_buckets(active_only=False),
            projects=config_repo.list_projects(active_only=False),
            statuses=config_repo.list_statuses(active_only=False),
            tags=tag_rows,
            filters={"bucket": bucket, "project": project, "tag": tag},
        )

    @app.route("/ideas/<idea_id>/edit", methods=["GET", "POST"])
    def edit_idea(idea_id: str):
        idea = ideas_repo.get_idea(idea_id)
        if not idea:
            abort(404)
        if request.method == "POST":
            bucket_id = request.form.get("bucket_id") or None
            project_id = request.form.get("project_id") or None
            status_id = request.form.get("status_id") or None
            ideas_repo.update_idea(
                idea_id,
                title=request.form["title"].strip(),
                notes=request.form.get("notes", "").strip(),
                bucket_id=bucket_id,
                project_id=project_id,
                status_id=status_id,
            )
            flash("Idea updated.")
            return redirect(url_for("index"))
        return render_template(
            "edit_idea.html",
            idea=idea,
            buckets=config_repo.list_buckets(active_only=False),
            projects=config_repo.list_projects(active_only=False),
            statuses=config_repo.list_statuses(active_only=False),
        )

    @app.route("/ideas/<idea_id>/delete", methods=["POST"])
    def delete_idea(idea_id: str):
        # Delete is gated behind the "are you sure?" modal in the UI; this route
        # only runs after the confirm action POSTs here.
        ideas_repo.delete_idea(idea_id)
        flash("Idea deleted.")
        return redirect(url_for("index"))

    @app.route("/projects", methods=["POST"])
    def add_project():
        name = request.form.get("name", "").strip()
        if name:
            config_repo.add_project(name)
            flash(f"Project '{name}' added.")
        return redirect(url_for("index"))

    @app.route("/projects/<project_id>/archive", methods=["POST"])
    def archive_project(project_id: str):
        config_repo.archive_project(project_id)
        flash("Project archived.")
        return redirect(url_for("index"))

    @app.route("/tags", methods=["POST"])
    def add_tag():
        name = request.form.get("name", "").strip()
        if name:
            config_repo.get_or_create_tag(name)
            flash(f"Tag '{name}' added.")
        return redirect(url_for("index"))

    return app


def main() -> None:
    run_guardrails()
    app = create_app()
    app.run(host=settings.dashboard_host, port=settings.dashboard_port, debug=False)


if __name__ == "__main__":
    main()
