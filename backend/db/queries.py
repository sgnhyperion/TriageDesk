"""
Thin query helpers over the connection pool. Owner: Member B.

Every tool / RAG / analytics function reads and writes through these three
helpers instead of managing connections itself. Keeping all SQL access in one
tiny surface makes the data layer easy to reason about, test, and later swap.

Pattern: parameterised SQL only (psycopg %s placeholders) — never string
interpolation — so we're injection-safe by construction.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Sequence

from backend.db.client import get_pool

Params = Sequence[Any] | None


def jsonable(value: Any) -> Any:
    """Recursively convert DB values (datetime/date/Decimal) into JSON-safe types.

    Tool outputs land in ToolResult.output and are persisted to jsonb / sent over
    the API, so timestamps must be ISO strings rather than Python datetimes.
    """
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def fetch_all(sql: str, params: Params = None) -> list[dict]:
    """Run a SELECT and return all rows as dicts."""
    with get_pool().connection() as conn:
        cur = conn.execute(sql, params or ())
        return cur.fetchall()


def fetch_one(sql: str, params: Params = None) -> dict | None:
    """Run a SELECT and return the first row as a dict (or None)."""
    with get_pool().connection() as conn:
        cur = conn.execute(sql, params or ())
        return cur.fetchone()


def execute(sql: str, params: Params = None) -> dict | None:
    """Run an INSERT/UPDATE/DELETE. Returns the first row if the statement has a
    RETURNING clause, else None. Commit happens when the pooled connection's
    context exits successfully.
    """
    with get_pool().connection() as conn:
        cur = conn.execute(sql, params or ())
        return cur.fetchone() if cur.description else None
