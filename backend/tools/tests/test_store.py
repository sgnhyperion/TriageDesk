"""Tests for the Postgres-backed store (Member B). DB only — no Gemini key."""
from __future__ import annotations

from contracts.schemas import (Classification, RouteDecision, Sentiment, Severity,
                               SupportState, TicketCategory, ToolName, ToolResult)
from backend import store
from backend.db import queries


def test_list_and_get():
    tickets = store.list_tickets()
    assert len(tickets) >= 10
    assert "TCK-1001" in {t["id"] for t in tickets}
    one = store.get_ticket("TCK-1001")
    assert one and one["subject"]
    assert store.get_ticket("NOPE") is None


def test_list_status_filter():
    resolved = store.list_tickets("resolved")
    assert len(resolved) >= 5 and all(t["status"] == "resolved" for t in resolved)


def test_create_ticket_resolves_customer_by_email():
    t = store.create_ticket("New issue", "body text", customer_email="alice@example.com")
    try:
        assert t["id"].startswith("TCK-")
        assert t["customer_id"] == "CUST-42"
        assert store.get_ticket(t["id"])["status"] == "open"
    finally:
        queries.execute("delete from tickets where id = %s", (t["id"],))


def test_save_state_persists_status_and_trace():
    t = store.create_ticket("Trace test", "b")
    try:
        st = store.new_state(t)
        st.classification = Classification(
            category=TicketCategory.BILLING, severity=Severity.HIGH,
            sentiment=Sentiment.NEGATIVE, confidence=0.9, in_scope=True,
            summary="duplicate charge")
        st.scratchpad.append(ToolResult(tool=ToolName.LOOKUP_ORDER, ok=True,
                                        output={"duplicate_charge": True}))
        st.scratchpad.append(ToolResult(tool=ToolName.PROCESS_REFUND, ok=True,
                                        output={"refund_id": "REF-x"}))
        st.route = RouteDecision.DONE
        st.final_reply = "Refunded."
        store.save_state(st)

        row = queries.fetch_one(
            "select status, category, final_reply from tickets where id = %s", (t["id"],))
        assert row["status"] == "resolved"
        assert row["category"] == "billing"
        assert row["final_reply"] == "Refunded."

        traces = queries.fetch_all(
            "select tool, ok from agent_traces where ticket_id = %s order by step", (t["id"],))
        assert [tr["tool"] for tr in traces] == ["lookup_order", "process_refund"]
    finally:
        queries.execute("delete from tickets where id = %s", (t["id"],))  # cascades traces
