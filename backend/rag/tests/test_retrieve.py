"""Tests for retrieve_kb + grounding threshold (Member B).

Needs key+DB (rag_env). Seeds the KB (idempotent) then checks a relevant query
grounds and an unrelated query does NOT — the no-hallucination guardrail.
"""
from __future__ import annotations

import pytest

from contracts.schemas import SupportState, ToolName
from backend.rag import retrieve, ingest

pytestmark = pytest.mark.usefixtures("rag_env")


def _state(subject, body=""):
    return SupportState(ticket_id="T", ticket_subject=subject, ticket_body=body)


@pytest.fixture(autouse=True)
def _seed_kb(rag_env):  # rag_env first -> skips cleanly when key/DB absent
    ingest.ingest_seed_kb()  # idempotent


def test_relevant_query_is_grounded():
    r = retrieve.retrieve_kb({"query": "How do I change my plan from Free to Pro?"}, _state("plan"))
    assert r.ok and r.tool == ToolName.RETRIEVE_KB
    assert r.output["has_grounding"] is True
    assert r.output["chunks"], "expected at least one retrieved chunk"
    assert r.output["top_score"] >= retrieve.GROUNDING_THRESHOLD


def test_refund_policy_query_grounded():
    r = retrieve.retrieve_kb({"query": "Are duplicate charges refundable?"}, _state("refund"))
    assert r.output["has_grounding"] is True
    titles = {c["document_title"] for c in r.output["chunks"]}
    assert any("Refund" in t for t in titles)


def test_unrelated_query_not_grounded():
    """A query with no KB support must NOT ground -> brain should escalate."""
    r = retrieve.retrieve_kb(
        {"query": "What is the airspeed velocity of an unladen swallow on Jupiter?"},
        _state("nonsense"))
    assert r.output["has_grounding"] is False
