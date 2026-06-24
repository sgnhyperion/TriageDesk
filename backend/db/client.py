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

    `connect_timeout` + the pool `timeout` keep an unreachable DB from blocking
    a request for ~30s: a tool call fails fast, dispatch() turns it into an
    `ok=False` ToolResult, and the brain degrades gracefully instead of hanging.
    """
    connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "8"))
    # Raise ivfflat.probes on every connection so KB retrieval has full recall at
    # the project's small KB scale (default probes=1 only scans one list, which
    # misses chunks when the table is tiny). Tunable via IVFFLAT_PROBES.
    options = f"-c ivfflat.probes={os.getenv('IVFFLAT_PROBES', '100')}"
    return ConnectionPool(
        conninfo=get_dsn(),
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row, "connect_timeout": connect_timeout, "options": options},
        timeout=float(os.getenv("DB_POOL_TIMEOUT", str(connect_timeout))),
        open=True,
    )


def close_pool() -> None:
    """Close the process-wide pool, if one was created.

    Short-lived scripts (setup, seed) should call this before exiting so the
    pool shuts its background threads down while the interpreter is still alive,
    instead of letting the destructor fire too late during finalization (which
    raises PythonFinalizationError on Python 3.14).
    """
    if get_pool.cache_info().currsize:
        get_pool().close()
        get_pool.cache_clear()


def healthcheck() -> bool:
    """True if the database is reachable (used by tests / a /health probe)."""
    try:
        with get_pool().connection() as conn:
            conn.execute("select 1")
        return True
    except Exception:
        return False
