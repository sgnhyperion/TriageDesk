"""
apply_schema.py — create the TriageDesk schema on the local Postgres.

Runs two SQL files in order against DATABASE_URL:
  1. backend/db/local_bootstrap.sql  — dev-only auth/roles shim (see that file)
  2. contracts/schema.sql            — the FROZEN database contract, unmodified

Usage (after `docker compose up -d`):
    python backend/db/apply_schema.py

This targets a FRESH database. The contract's `create policy` statements are not
guarded with IF NOT EXISTS, so to re-apply cleanly, reset the volume first:
    docker compose down -v && docker compose up -d && python backend/db/apply_schema.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import psycopg
except ModuleNotFoundError:
    sys.exit("psycopg not installed — run: pip install -r backend/requirements.txt")

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/triagedesk"

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
_BOOTSTRAP = _HERE / "local_bootstrap.sql"
_CONTRACT_SCHEMA = _REPO_ROOT / "contracts" / "schema.sql"


def _dsn() -> str:
    # backend/__init__.py loads .env on import; but this script may run standalone,
    # so fall back to the env var, then the local compose default.
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


def main() -> None:
    dsn = _dsn()
    files = [_BOOTSTRAP, _CONTRACT_SCHEMA]
    print(f"Applying schema to: {dsn.rsplit('@', 1)[-1]}")
    with psycopg.connect(dsn, autocommit=True) as conn:
        for sql_file in files:
            sql = sql_file.read_text()
            try:
                conn.execute(sql)
            except psycopg.errors.DuplicateObject as exc:
                sys.exit(
                    f"\n{sql_file.name} failed — an object already exists "
                    f"({exc}).\nThe DB is not fresh. Reset it with:\n"
                    "  docker compose down -v && docker compose up -d\n"
                    "then re-run this script."
                )
            print(f"  ✓ applied {sql_file.relative_to(_REPO_ROOT)}")
    print("Schema applied.")


if __name__ == "__main__":
    main()
