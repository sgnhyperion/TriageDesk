"""Shared fixtures for Member B's tool tests.

These are integration tests against the local Postgres (docker compose + seed).
If the DB isn't reachable, the whole module is skipped with a clear hint rather
than failing — so `pytest` stays green for teammates who haven't started the DB.

Kept under backend/tools/tests/ to avoid colliding with Member C's eval suite in
backend/tests/.
"""
from __future__ import annotations

import pytest

from backend.db import client, seed


@pytest.fixture(scope="session", autouse=True)
def _db_ready():
    if not client.healthcheck():
        pytest.skip(
            "local Postgres not reachable — run `docker compose up -d` and "
            "`python backend/db/apply_schema.py` first",
            allow_module_level=True,
        )
    seed.seed_all()  # idempotent; guarantees the rows the tests assert on exist
