"""Fixtures for RAG tests (Member B).

RAG needs BOTH the local Postgres (pgvector) AND a real Gemini key for
embeddings. If either is missing, these tests skip with a clear hint rather than
failing — so `pytest` stays green before the key is added.
"""
from __future__ import annotations

import os

import pytest

from backend.db import client


@pytest.fixture(scope="session", autouse=True)
def _rag_ready():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set — RAG tests need Gemini embeddings")
    if not client.healthcheck():
        pytest.skip("local Postgres not reachable — run docker compose up + apply_schema")
