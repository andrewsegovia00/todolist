"""Apply SQL migrations in order.

Supabase's PostgREST client can't run arbitrary DDL, so migrations are applied
over a direct Postgres connection. Provide the connection string as DATABASE_URL
(Supabase: Project Settings -> Database -> Connection string -> URI).

    DATABASE_URL=postgresql://... python -m db.migrate

If `psycopg` is not installed or DATABASE_URL is unset, this prints the files to
paste into the Supabase SQL editor instead — so it always tells you what to do.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _print_manual_instructions(files: list[Path]) -> None:
    print("DATABASE_URL not set (or psycopg missing).")
    print("Apply these migrations in order via the Supabase SQL editor:\n")
    for f in files:
        print(f"  - {f.relative_to(Path.cwd()) if f.is_relative_to(Path.cwd()) else f}")
    print("\nThen run: python -m db.seed")


def main() -> int:
    files = migration_files()
    if not files:
        print("No migration files found.")
        return 1

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        _print_manual_instructions(files)
        return 0

    try:
        import psycopg  # type: ignore
    except ImportError:
        print("psycopg not installed. `pip install psycopg[binary]` or apply manually.\n")
        _print_manual_instructions(files)
        return 0

    with psycopg.connect(dsn, autocommit=True) as conn:
        for f in files:
            print(f"Applying {f.name} ...")
            conn.execute(f.read_text())
    print(f"Applied {len(files)} migration(s).")
    print("Next: python -m db.seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
