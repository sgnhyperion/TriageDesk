"""Tests for send_email (key-guarded stub path). Owner: Member B.

Runs against the DB only (no Gemini key needed). With no RESEND_API_KEY the tool
records intent + DB rows but does not send — which is exactly what we assert.
"""
from __future__ import annotations

import os

import pytest

from contracts.schemas import SupportState, ToolName
from backend.integrations import email_resend
from backend.db import queries

_MARKER = "Thanks for reaching out — your duplicate charge has been refunded."


@pytest.fixture(autouse=True)
def _no_resend_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)


@pytest.fixture
def cleanup():
    yield
    queries.execute("delete from messages where ticket_id = 'TCK-1001' and body = %s", (_MARKER,))
    queries.execute("delete from audit_log where ticket_id = 'TCK-1001' and action = 'send_email'")


def test_send_email_stub_records_intent_and_rows(cleanup):
    # TCK-1001 -> CUST-42 -> alice@example.com (recipient resolved from DB)
    state = SupportState(ticket_id="TCK-1001", ticket_subject="Charged twice",
                         ticket_body="b", customer_id="CUST-42")
    r = email_resend.send_email({"body": _MARKER}, state)

    assert r.ok and r.tool == ToolName.SEND_EMAIL
    assert r.output["sent"] is False and r.output["mock"] is True
    assert r.output["to"] == "alice@example.com"  # resolved from customers table
    assert "RESEND_API_KEY not set" in r.output["error"]

    msg = queries.fetch_one(
        "select direction, sender, body from messages "
        "where ticket_id = 'TCK-1001' and body = %s", (_MARKER,))
    assert msg["direction"] == "outbound" and msg["sender"] == "agent"

    audit = queries.fetch_one(
        "select detail from audit_log where ticket_id = 'TCK-1001' "
        "and action = 'send_email' order by created_at desc")
    assert audit["detail"]["sent"] is False and audit["detail"]["to"] == "alice@example.com"


def test_send_email_explicit_recipient(cleanup):
    state = SupportState(ticket_id="TCK-1001", ticket_subject="x", ticket_body="b")
    r = email_resend.send_email({"to": "someone@else.com", "body": _MARKER}, state)
    assert r.output["to"] == "someone@else.com" and r.output["sent"] is False
