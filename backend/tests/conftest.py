"""
Shared pytest fixtures. Owner: Member A.

Two tiers of tests live here:

  * Orchestration unit tests (supervisor, graph, llm, resilience, observability)
    run fully OFFLINE — no LLM key, no database. The autouse fixture clears
    credentials and fast-fails any DB tool call (the brain degrades gracefully).

  * API / auth tests are INTEGRATION tests: Member B's `store` and KB endpoints
    are DB-backed, so they need Postgres. They are skipped by default and run
    when you point them at a database:

        TRIAGEDESK_TEST_DB="postgresql://..." pytest backend/tests -q

Live LLM verification is separate: `python -m backend.scripts.smoke`.
"""
import os

import pytest

# Set to a DATABASE_URL to run the DB-backed API/auth integration tests.
_TEST_DB = os.getenv("TRIAGEDESK_TEST_DB")
_DB_BACKED_MODULES = {"test_api.py", "test_auth.py"}


def pytest_collection_modifyitems(config, items):
    """Skip DB-backed integration tests unless a test database is configured."""
    if _TEST_DB:
        return
    skip_db = pytest.mark.skip(
        reason="store/KB are DB-backed — set TRIAGEDESK_TEST_DB to run these integration tests")
    for item in items:
        if os.path.basename(str(item.fspath)) in _DB_BACKED_MODULES:
            item.add_marker(skip_db)


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    # Deterministic + offline: no live LLM, no tracing uploads, auth off unless a
    # test opts in (test_auth sets SUPABASE_JWT_SECRET itself).
    for var in ("LLM_PROVIDER", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
                "LANGCHAIN_API_KEY", "LANGSMITH_API_KEY",
                "SUPABASE_URL", "SUPABASE_JWKS_URL", "SUPABASE_JWT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")

    if _TEST_DB:
        monkeypatch.setenv("DATABASE_URL", _TEST_DB)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # No DB: brain tests still dispatch DB-backed tools — fail those fast so the
        # loop degrades gracefully (ok=False) instead of blocking on a connection.
        def _no_database(*_a, **_k):
            raise ConnectionError("database disabled in unit tests")

        monkeypatch.setattr("backend.db.queries.get_pool", _no_database, raising=False)
