"""
API integration tests for the FastAPI routes. Owner: Member A.

Drive the real app (graph engine + read-model store) over HTTP via TestClient,
on the no-key fallback brain. Each test creates its own ticket so the shared
graph checkpointer / store don't leak between tests.

Run from repo root:  pytest backend/tests -q
"""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _new_ticket(subject: str, body: str) -> str:
    resp = client.post("/tickets", json={"subject": subject, "body": body})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_inbox_lists_seeded_tickets():
    ids = [t["id"] for t in client.get("/tickets").json()]
    assert "TCK-1001" in ids


def test_run_pauses_for_human_then_decision_completes():
    tid = _new_ticket("How do I upgrade?", "I want to move to Pro")

    run = client.post(f"/tickets/{tid}/run").json()
    assert run["route"] == "await_human"
    assert run["awaiting_action"] == "send_email"
    assert run["draft"] is not None
    assert run["final_reply"] is None

    trace = client.get(f"/tickets/{tid}/trace").json()
    # reasoned trace includes the pending high-impact step, each with a reason
    assert [s["tool"] for s in trace] == ["retrieve_kb", "draft_reply", "send_email"]
    assert all(s["reason"] for s in trace)

    done = client.post(f"/tickets/{tid}/decision", json={"action": "approve"}).json()
    assert done["route"] == "done"
    assert done["final_reply"] is not None


def test_rerun_while_awaiting_is_idempotent():
    tid = _new_ticket("Billing question", "why was I charged")
    first = client.post(f"/tickets/{tid}/run").json()
    again = client.post(f"/tickets/{tid}/run").json()
    assert again["route"] == "await_human"
    assert again["step_count"] == first["step_count"]  # did not advance


def test_decision_without_run_is_404():
    tid = _new_ticket("Need help", "something")
    resp = client.post(f"/tickets/{tid}/decision", json={"action": "approve"})
    assert resp.status_code == 404


def test_decision_when_not_awaiting_is_409():
    tid = _new_ticket("Upgrade", "move me to pro")
    client.post(f"/tickets/{tid}/run")
    client.post(f"/tickets/{tid}/decision", json={"action": "approve"})  # -> done
    second = client.post(f"/tickets/{tid}/decision", json={"action": "approve"})
    assert second.status_code == 409


def test_out_of_scope_ticket_escalates_without_drafting():
    tid = _new_ticket("Homework", "write my 2000 word essay on the French Revolution")
    run = client.post(f"/tickets/{tid}/run").json()
    assert run["route"] == "escalate"
    assert run["awaiting_action"] is None
    assert run["draft"] is None


def test_unknown_ticket_run_is_404():
    assert client.post("/tickets/NOPE-9999/run").status_code == 404


def test_ticket_detail_reflects_run_state():
    tid = _new_ticket("Upgrade plan", "how do I upgrade")
    # Before a run: bare ticket, no draft.
    before = client.get(f"/tickets/{tid}").json()
    assert before["draft"] is None and before["status"] == "open"

    client.post(f"/tickets/{tid}/run")
    after = client.get(f"/tickets/{tid}").json()
    assert after["status"] == "awaiting_human"
    assert after["awaiting_action"] == "send_email"
    assert after["draft"] is not None
    assert after["classification"] is not None
    assert after["escalated"] is False


def test_kb_upload_delegates_to_ingest():
    # Dev mode => the dependency yields an admin, so the route runs and delegates
    # to Member B's ingest stub, which is not implemented yet (clean 501).
    resp = client.post(
        "/kb/upload",
        files={"file": ("kb.txt", b"hello world", "text/plain")},
        data={"title": "Help doc"},
    )
    assert resp.status_code == 501


def test_kb_upload_requires_a_file():
    assert client.post("/kb/upload", data={"title": "no file"}).status_code == 422
