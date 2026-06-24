"""
HITL pause/resume persistence for the LangGraph supervisor. Owner: Member A.

`interrupt()` (in graph.py) pauses the graph before a high-impact action; the
checkpointer is what persists that paused state so a later HTTP request
(POST /tickets/{id}/decision) can resume the exact same run.

- With DATABASE_URL set → LangGraph's Postgres checkpointer (survives restarts,
  shared across processes). Requires `langgraph-checkpoint-postgres`.
- Otherwise → an in-memory saver, so the skeleton (and tests) run HITL with no DB.

All imports are lazy so the backend imports cleanly without langgraph installed.
"""
import logging
import os

# Placeholder value in .env.example — treat as "not configured".
_PLACEHOLDER_DBS = {"", "postgresql://..."}


def _database_url() -> str | None:
    url = os.getenv("DATABASE_URL")
    return None if (url or "") in _PLACEHOLDER_DBS else url


def postgres_available() -> bool:
    return _database_url() is not None


def _serde():
    """Serializer that explicitly allows our frozen-contract types.

    The graph state holds Pydantic models / enums from contracts.schemas. The
    checkpointer serializes them; without an allow-list, newer langgraph logs a
    deprecation notice per type and will eventually block them. allowed_msgpack_
    modules=True opts them in (verified to round-trip and to pass strict mode).
    We also raise the serde logger's threshold to silence the now-redundant
    per-type deprecation notice.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    logging.getLogger("langgraph.checkpoint.serde.jsonplus").setLevel(logging.ERROR)
    return JsonPlusSerializer(allowed_msgpack_modules=True)


def get_checkpointer():
    """Return a checkpointer: Postgres when DATABASE_URL is set, else in-memory."""
    serde = _serde()
    url = _database_url()
    if url is not None:
        try:
            import psycopg
            from langgraph.checkpoint.postgres import PostgresSaver

            # Hold an explicit long-lived connection for the process. autocommit is
            # required for setup() DDL + checkpoint writes; prepare_threshold=0 keeps
            # us compatible with connection poolers (e.g. Supabase's pooler).
            conn = psycopg.connect(url, autocommit=True, prepare_threshold=0, connect_timeout=15)
            saver = PostgresSaver(conn)
            saver.serde = serde
            saver.setup()  # idempotent: creates the checkpoint tables if absent
            return saver
        except Exception as exc:  # noqa: BLE001 - fall back rather than crash boot
            print(f"[checkpointer] Postgres unavailable ({exc}); using in-memory saver.")

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver(serde=serde)
