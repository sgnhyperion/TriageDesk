"""Tests for request_more_info. Owner: Member B."""
from __future__ import annotations

from contracts.schemas import SupportState, ToolName
from backend.tools import info
from backend.db import queries


def test_request_more_info_persists_message():
    # TCK-1004 is the seeded vague ticket.
    state = SupportState(ticket_id="TCK-1004", ticket_subject="It's not working",
                         ticket_body="nothing works")
    try:
        r = info.request_more_info({"question": "Which screen shows the error?"}, state)
        assert r.ok and r.tool == ToolName.REQUEST_MORE_INFO
        assert r.output["awaiting_reply"] is True
        assert r.output["persisted"] is True
        msg = queries.fetch_one(
            "select direction, sender, body from messages "
            "where ticket_id = 'TCK-1004' order by created_at desc")
        assert msg["direction"] == "outbound" and msg["body"] == "Which screen shows the error?"
    finally:
        queries.execute("delete from messages where ticket_id = 'TCK-1004'")


def test_request_more_info_unknown_ticket_does_not_persist():
    state = SupportState(ticket_id="TCK-UNKNOWN", ticket_subject="x", ticket_body="y")
    r = info.request_more_info({}, state)
    assert r.ok and r.output["persisted"] is False and r.output["awaiting_reply"] is True
