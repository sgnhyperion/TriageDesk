"""Gemini embeddings for RAG. Owner: Member B.

Thin wrapper over get_embeddings() so the rest of the RAG pipeline (ingest +
retrieve) never touches the provider directly. text-embedding-004 -> 768-dim
vectors, matching the kb_chunks.embedding column in schema.sql.
"""
from __future__ import annotations

from functools import lru_cache

from backend.llm import get_embeddings

EMBED_DIM = 768  # Gemini text-embedding-004; must match vector(768) in schema.sql


@lru_cache(maxsize=1)
def _client():
    return get_embeddings()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of chunk texts (used during ingestion)."""
    if not texts:
        return []
    return _client().embed_documents(texts)


def embed_query(text: str) -> list[float]:
    """Embed a single query string (used by retrieve_kb)."""
    return _client().embed_query(text)
