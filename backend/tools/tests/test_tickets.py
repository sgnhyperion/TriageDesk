"""Tests for search_past_tickets + create_bug_report (Member B)."""
from __future__ import annotations

from contracts.schemas import SupportState, ToolName
from backend.tools import tickets


def _state(ticket_id="TCK-NEW", subject="s", body="b", customer_id=None):
    return SupportState(ticket_id=ticket_id, ticket_subject=subject,
                        ticket_body=body, customer_id=customer_id)


def test_search_finds_known_pdf_crash():
    """A new PDF-export crash ticket should match the resolved TCK-0901."""
    st = _state(subject="App crashes when I export to PDF",
                body="Every time I click Export > PDF the app crashes.")
    r = tickets.search_past_tickets({}, st)
    assert r.ok and r.tool == ToolName.SEARCH_PAST_TICKETS
    assert r.output["has_match"] is True
    assert any(m["id"] == "TCK-0901" for m in r.output["matches"])


def test_search_excludes_current_ticket():
    st = _state(ticket_id="TCK-0901", subject="PDF export crashes", body="crash on export")
    r = tickets.search_past_tickets({}, st)
    assert all(m["id"] != "TCK-0901" for m in r.output["matches"])


def test_search_no_match_for_unrelated():
    st = _state(subject="zzqq nonsense unrelated gibberish", body="xyzzy plugh")
    r = tickets.search_past_tickets({}, st)
    assert r.ok and r.output["has_match"] is False


def test_create_bug_report():
    st = _state(subject="New crash on import", body="App crashes importing CSV")
    r = tickets.create_bug_report({"severity": "high"}, st)
    assert r.ok and r.tool == ToolName.CREATE_BUG_REPORT
    assert r.output["bug_id"].startswith("BUG-")
    assert r.output["status"] == "filed"
    assert r.output["severity"] == "high"
