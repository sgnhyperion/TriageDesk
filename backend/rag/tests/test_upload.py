"""Tests for KB upload + document listing (Member B). Gated on key+DB."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.rag import ingest
from backend.db import queries

pytestmark = pytest.mark.usefixtures("rag_env")


def test_upload_indexes_and_lists():
    res = ingest.save_and_ingest_upload(
        "upload_test.md",
        b"# Upgrades\nUpgrades to the Pro plan take effect immediately.",
        title="Upload Test")
    saved = Path(ingest._UPLOAD_DIR) / "upload_test.md"
    try:
        assert res["chunks_indexed"] >= 1
        assert saved.exists()  # file persisted to local storage
        docs = ingest.list_kb_documents()
        assert any(d["title"] == "Upload Test" for d in docs)
    finally:
        queries.execute("delete from kb_documents where id = %s", (res["document_id"],))
        saved.unlink(missing_ok=True)
