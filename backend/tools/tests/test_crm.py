"""Unit/integration tests for the CRM lookup tools (Member B)."""
from __future__ import annotations

from contracts.schemas import SupportState, ToolName
from backend.tools import crm


def _state(customer_id=None):
    return SupportState(ticket_id="T", ticket_subject="s", ticket_body="b", customer_id=customer_id)


def test_lookup_customer_found():
    r = crm.lookup_customer({}, _state("CUST-42"))
    assert r.ok and r.tool == ToolName.LOOKUP_CUSTOMER
    assert r.output["found"] is True
    assert r.output["customer"]["id"] == "CUST-42"
    assert r.output["customer"]["plan"] == "pro"
    assert r.output["order_count"] >= 2  # duplicate charge


def test_lookup_customer_not_found():
    r = crm.lookup_customer({"customer_id": "CUST-DOES-NOT-EXIST"}, _state())
    assert r.ok and r.output["found"] is False


def test_lookup_customer_missing_id():
    r = crm.lookup_customer({}, _state(customer_id=None))
    assert r.ok and r.output["found"] is False


def test_lookup_order_detects_duplicate_charge():
    """The headline billing case: CUST-42 has two identical paid charges."""
    r = crm.lookup_order({}, _state("CUST-42"))
    assert r.ok and r.output["duplicate_charge"] is True
    assert len(r.output["duplicate_order_ids"]) == 2
    assert r.output["duplicate_amount_cents"] == 2900  # one extra $29 charge


def test_lookup_order_no_duplicate_for_single_charge():
    r = crm.lookup_order({}, _state("CUST-7"))
    assert r.ok and r.output["duplicate_charge"] is False


def test_lookup_order_timestamps_are_iso_strings():
    r = crm.lookup_order({}, _state("CUST-42"))
    charged_at = r.output["orders"][0]["charged_at"]
    assert isinstance(charged_at, str)  # jsonable() converted datetime -> ISO


def test_check_subscription_status():
    r = crm.check_subscription_status({}, _state("CUST-42"))
    assert r.ok and r.output["found"] is True
    assert r.output["active"] is True
    assert r.output["subscriptions"][0]["plan"] == "pro"
