"""
Postgres connection layer. Owner: Member B.

We talk to Postgres directly with psycopg over DATABASE_URL, using a small
connection pool. This is deliberately provider-agnostic: the SAME code works
against our local pgvector container today and a real Supabase Postgres
connection string later — only DATABASE_URL changes.

Tools/RAG/analytics never open connections themselves; they call the helpers in
backend/db/queries.py, which borrow from this pool.
"""
from __future__ import annotations

import os
from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Matches docker-compose.yml. backend/__init__.py loads .env, so a DATABASE_URL
# there (e.g. a real Supabase string) transparently overrides this default.
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/triagedesk"


def get_dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


@lru_cache(maxsize=1)
def get_pool() -> ConnectionPool:
    """Lazily create one process-wide connection pool.

    Rows come back as dicts (dict_row) so callers get column-name access.
    """
    return ConnectionPool(
        conninfo=get_dsn(),
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row},
        open=True,
    )


def healthcheck() -> bool:
    """True if the database is reachable (used by tests / a /health probe)."""
    try:
        with get_pool().connection() as conn:
            conn.execute("select 1")
        return True
    except Exception:
        return False
