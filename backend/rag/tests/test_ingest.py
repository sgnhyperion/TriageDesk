"""Tests for the KB ingest pipeline (Member B).

chunk_text is pure (always runs); the embed+index tests need key+DB (skip via
conftest until GEMINI_API_KEY is set).
"""
from __future__ import annotations

from backend.rag import ingest
from backend.db import queries


def test_chunking_overlap_and_size():
    text = " ".join(f"w{i}" for i in range(450))
    chunks = ingest.chunk_text(text, max_words=200, overlap=40)
    assert [len(c.split()) for c in chunks] == [200, 200, 130]
    c0, c1 = chunks[0].split(), chunks[1].split()
    assert c0[-40:] == c1[:40]  # windows overlap


def test_chunking_empty():
    assert ingest.chunk_text("") == []


def test_ingest_document_indexes_chunks(rag_env):
    doc = ingest.ingest_document(
        "Test Doc",
        b"Refunds for duplicate charges are always issued in full. "
        b"Pro plans can be refunded within 14 days if unused.",
        source_path="test/inline")
    try:
        assert doc["chunks_indexed"] >= 1
        rows = queries.fetch_all(
            "select content, embedding is not null as has_vec from kb_chunks "
            "where document_id = %s", (doc["document_id"],))
        assert len(rows) == doc["chunks_indexed"]
        assert all(r["has_vec"] for r in rows)  # every chunk embedded
    finally:
        queries.execute("delete from kb_documents where id = %s", (doc["document_id"],))
