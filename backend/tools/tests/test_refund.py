"""Tests for process_refund (mock + audit). Owner: Member B.

Uses throwaway customer/order/ticket rows so it never mutates the seed data the
other tests rely on, and cleans up afterwards.
"""
from __future__ import annotations

import pytest

from contracts.schemas import SupportState, ToolName, ToolResult
from backend.tools import refund
from backend.db import queries


@pytest.fixture
def temp_order():
    queries.execute("insert into customers (id,name,email,plan) values "
                    "('CUST-RT','RT','rt@test.dev','pro') on conflict (id) do nothing")
    queries.execute("insert into orders (id,customer_id,amount_cents,status) values "
                    "('ORD-RT','CUST-RT',2900,'paid') on conflict (id) do nothing")
    yield "ORD-RT"
    queries.execute("delete from refunds where order_id = 'ORD-RT'")
    queries.execute("delete from audit_log where detail->>'order_id' = 'ORD-RT'")
    queries.execute("delete from orders where id = 'ORD-RT'")
    queries.execute("delete from customers where id = 'CUST-RT'")


def test_refund_from_scratchpad_duplicate(temp_order):
    """Brain ran lookup_order (duplicate found) -> refund picks it up from scratchpad."""
    state = SupportState(ticket_id="TCK-RT", ticket_subject="s", ticket_body="b")
    state.scratchpad.append(ToolResult(
        tool=ToolName.LOOKUP_ORDER, ok=True,
        output={"duplicate_order_ids": [temp_order], "duplicate_amount_cents": 2900}))

    r = refund.process_refund({}, state)
    assert r.ok and r.tool == ToolName.PROCESS_REFUND
    assert r.output["status"] == "processed_mock"
    assert r.output["amount_cents"] == 2900
    assert r.output["refund_id"].startswith("REF-")
    assert r.output["mock"] is True

    # refunds row persisted
    row = queries.fetch_one("select status, amount_cents from refunds where id = %s",
                            (r.output["refund_id"],))
    assert row["status"] == "processed" and row["amount_cents"] == 2900
    # order marked refunded
    order = queries.fetch_one("select status from orders where id = %s", (temp_order,))
    assert order["status"] == "refunded"
    # audit entry written
    audit = queries.fetch_one(
        "select action from audit_log where detail->>'order_id' = %s order by created_at desc",
        (temp_order,))
    assert audit["action"] == "process_refund"
    # in-memory audit trail updated
    assert any("process_refund" in line for line in state.audit_log)


def test_refund_explicit_args(temp_order):
    state = SupportState(ticket_id="TCK-RT", ticket_subject="s", ticket_body="b")
    r = refund.process_refund({"order_id": temp_order, "amount_cents": 1500}, state)
    assert r.ok and r.output["amount_cents"] == 1500 and r.output["order_id"] == temp_order
