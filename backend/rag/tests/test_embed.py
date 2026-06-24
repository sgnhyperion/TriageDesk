"""Tests for Gemini embeddings (Member B). Skipped until GEMINI_API_KEY is set."""
from __future__ import annotations

import pytest

from backend.rag import embed

pytestmark = pytest.mark.usefixtures("rag_env")  # all need a real key


def test_embed_query_dim():
    vec = embed.embed_query("How do I change my plan?")
    assert isinstance(vec, list) and len(vec) == embed.EMBED_DIM == 768


def test_embed_texts_batch():
    vecs = embed.embed_texts(["refunds for duplicate charges", "exporting to PDF"])
    assert len(vecs) == 2 and all(len(v) == 768 for v in vecs)


def test_embed_empty_returns_empty():
    assert embed.embed_texts([]) == []
