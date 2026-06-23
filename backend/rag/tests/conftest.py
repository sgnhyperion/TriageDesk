"""Fixtures for RAG tests (Member B).

The embed/index/retrieve tests need BOTH the local Postgres (pgvector) AND a real
Gemini key. They request the `rag_env` fixture, which skips with a clear hint if
either is missing — so `pytest` stays green before the key is added. Pure-Python
tests (e.g. chunk_text) don't request it and always run.
"""
from __future__ import annotations

import os

import pytest

from backend.db import client


@pytest.fixture
def rag_env():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set — needs Gemini embeddings")
    if not client.healthcheck():
        pytest.skip("local Postgres not reachable — run docker compose up + apply_schema")
