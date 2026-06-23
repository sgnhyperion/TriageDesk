"""
FastAPI routes implementing contracts/openapi.yaml. Owner: Member A.

These work on the stub store + stub brain so the frontend (Member C) has a live
API to build against immediately. Swap stubs for real pieces as they land.
"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from contracts.schemas import HumanAction
from backend import store, supervisor, analytics
from backend.agents import triage
from backend.rag import ingest

router = APIRouter()


# --- request bodies ---------------------------------------------------------
class CreateTicketRequest(BaseModel):
    subject: str
    body: str
    customer_email: str | None = None


class DecisionRequest(BaseModel):
    action: HumanAction
    edited_reply: str | None = None


# --- helpers ----------------------------------------------------------------
def _run_result(state) -> dict:
    return {
        "ticket_id": state.ticket_id,
        "route": state.route.value,
        "awaiting_action": state.awaiting_action.value if state.awaiting_action else None,
        "draft": state.draft.model_dump() if state.draft else None,
        "guardrail_result": state.guardrail_result.model_dump() if state.guardrail_result else None,
        "final_reply": state.final_reply,
        "step_count": state.step_count,
    }


def _trace(state) -> list[dict]:
    return [
        {"step": i + 1, "tool": r.tool.value, "reason": "", "args": {}, "result": r.output, "ok": r.ok}
        for i, r in enumerate(state.scratchpad)
    ]


# --- endpoints --------------------------------------------------------------
@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/tickets")
def list_tickets(status: str | None = None):
    return store.list_tickets(status)


@router.post("/tickets", status_code=201)
def create_ticket(req: CreateTicketRequest):
    return store.create_ticket(req.subject, req.body, req.customer_email)


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "ticket not found")
    return ticket


@router.post("/tickets/{ticket_id}/run")
def run_ticket(ticket_id: str):
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "ticket not found")
    state = store.new_state(ticket)
    state.classification = triage.classify(state)  # optional first triage pass
    state = supervisor.run(state)
    store.save_state(state)
    return _run_result(state)


@router.get("/tickets/{ticket_id}/trace")
def get_trace(ticket_id: str):
    state = store.get_state(ticket_id)
    if not state:
        raise HTTPException(404, "no run for this ticket yet")
    return _trace(state)


@router.post("/tickets/{ticket_id}/decision")
def decide(ticket_id: str, req: DecisionRequest):
    state = store.get_state(ticket_id)
    if not state:
        raise HTTPException(404, "no run for this ticket yet")
    state = supervisor.resume(state, req.action, req.edited_reply)
    store.save_state(state)
    return _run_result(state)


@router.get("/kb/documents")
def list_kb_documents():
    return ingest.list_kb_documents()


@router.post("/kb/upload")
async def upload_kb_document(file: UploadFile = File(...), title: str | None = Form(None)):
    """Admin KB upload: file -> chunk -> embed -> index, searchable live."""
    file_bytes = await file.read()
    try:
        return ingest.save_and_ingest_upload(file.filename, file_bytes, title=title)
    except Exception as exc:
        raise HTTPException(400, f"KB ingest failed: {exc}")


@router.get("/analytics")
def get_analytics():
    return analytics.get_analytics()
