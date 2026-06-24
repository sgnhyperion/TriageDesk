"""
FastAPI routes implementing contracts/openapi.yaml. Owner: Member A.

Execution engine: the LangGraph supervisor graph (backend/graph.py) drives each
ticket, with its checkpointer persisting paused state by thread_id=ticket_id so
HITL resume works across separate HTTP requests. Member B's `store` is used as
the read model for the inbox / detail / trace endpoints (swapped for Supabase
later). If langgraph isn't importable, we fall back to the in-process
supervisor loop so the skeleton still runs.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from contracts.schemas import HumanAction, RouteDecision
from backend import analytics, graph as graph_mod, store, supervisor
from backend.agents import triage
from backend.auth import AuthUser, get_current_user, require_admin
from backend.rag import ingest

router = APIRouter()

# RouteDecision -> the ticket status vocabulary in openapi.yaml.
_ROUTE_STATUS = {
    RouteDecision.CONTINUE: "in_progress",
    RouteDecision.AWAIT_HUMAN: "awaiting_human",
    RouteDecision.DONE: "resolved",
    RouteDecision.ESCALATE: "escalated",
    RouteDecision.REFUSE: "refused",
}

# Prefer the real LangGraph engine; fall back to the in-process loop if absent.
_USE_GRAPH = graph_mod.graph_available()


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


def _ticket_detail(ticket: dict, state) -> dict:
    """Full Ticket per openapi.yaml: raw ticket fields + live run state when present."""
    detail = {
        "id": ticket["id"],
        "customer_id": ticket.get("customer_id"),
        "subject": ticket["subject"],
        "body": ticket["body"],
        "status": ticket.get("status", "open"),
        "classification": None,
        "draft": None,
        "guardrail_result": None,
        "awaiting_action": None,
        "final_reply": None,
        "escalated": False,
        "created_at": ticket.get("created_at"),
    }
    if state is not None:
        detail.update({
            "status": _ROUTE_STATUS.get(state.route, detail["status"]),
            "classification": state.classification.model_dump() if state.classification else None,
            "draft": state.draft.model_dump() if state.draft else None,
            "guardrail_result": state.guardrail_result.model_dump() if state.guardrail_result else None,
            "awaiting_action": state.awaiting_action.value if state.awaiting_action else None,
            "final_reply": state.final_reply,
            "escalated": state.escalated,
        })
    return detail


def _trace(state) -> list[dict]:
    return [
        {"step": i + 1, "tool": r.tool.value, "reason": "", "args": {}, "result": r.output, "ok": r.ok}
        for i, r in enumerate(state.scratchpad)
    ]


def _start_run(state):
    """Run the brain via the graph engine (or the in-process loop as fallback)."""
    if _USE_GRAPH:
        return graph_mod.start_run(graph_mod.get_graph(), state)
    return supervisor.run(state)


def _resume(state, action: HumanAction, edited_reply: str | None):
    if _USE_GRAPH:
        return graph_mod.submit_decision(graph_mod.get_graph(), state.ticket_id, action, edited_reply)
    return supervisor.resume(state, action, edited_reply)


# --- endpoints --------------------------------------------------------------
@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/tickets", dependencies=[Depends(get_current_user)])
def list_tickets(status: str | None = None):
    return store.list_tickets(status)


@router.post("/tickets", status_code=201, dependencies=[Depends(get_current_user)])
def create_ticket(req: CreateTicketRequest):
    return store.create_ticket(req.subject, req.body, req.customer_email)


@router.get("/tickets/{ticket_id}", dependencies=[Depends(get_current_user)])
def get_ticket(ticket_id: str):
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "ticket not found")
    return _ticket_detail(ticket, store.get_state(ticket_id))


@router.post("/tickets/{ticket_id}/run", dependencies=[Depends(get_current_user)])
def run_ticket(ticket_id: str):
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "ticket not found")

    # If a run already paused for human approval, return it rather than re-running.
    existing = store.get_state(ticket_id)
    if existing and existing.route == RouteDecision.AWAIT_HUMAN:
        return _run_result(existing)

    state = store.new_state(ticket)
    state.classification = triage.classify(state)  # optional first triage pass
    state = _start_run(state)
    store.save_state(state)  # read model for /trace + detail
    return _run_result(state)


@router.get("/tickets/{ticket_id}/trace", dependencies=[Depends(get_current_user)])
def get_trace(ticket_id: str):
    # Prefer the reasoned trace reconstructed from the graph checkpoint history
    # (includes each step's reason + args); fall back to the scratchpad-only view.
    if _USE_GRAPH:
        try:
            steps = graph_mod.reasoned_trace(graph_mod.get_graph(), ticket_id)
            if steps:
                return steps
        except Exception:  # noqa: BLE001 - never fail the UI over trace reconstruction
            pass
    state = store.get_state(ticket_id)
    if not state:
        raise HTTPException(404, "no run for this ticket yet")
    return _trace(state)


@router.post("/tickets/{ticket_id}/decision", dependencies=[Depends(get_current_user)])
def decide(ticket_id: str, req: DecisionRequest):
    state = store.get_state(ticket_id)
    if not state:
        raise HTTPException(404, "no run for this ticket yet")
    if state.route != RouteDecision.AWAIT_HUMAN:
        raise HTTPException(409, "ticket is not awaiting a human decision")
    state = _resume(state, req.action, req.edited_reply)
    store.save_state(state)
    return _run_result(state)


@router.get("/kb/documents", dependencies=[Depends(require_admin)])
def list_kb_documents():
    return []  # TODO(Member B)


@router.post("/kb/upload", status_code=201)
async def upload_kb(
    file: UploadFile = File(...),
    title: str = Form(...),
    user: AuthUser = Depends(require_admin),
):
    """Admin: upload a KB doc → chunk + embed + index (delegates to Member B's ingest)."""
    contents = await file.read()
    try:
        return ingest.ingest_document(title=title, file_bytes=contents, uploaded_by=user.id)
    except NotImplementedError:
        raise HTTPException(501, "KB ingestion not implemented yet (Member B)")


@router.get("/analytics", dependencies=[Depends(get_current_user)])
def get_analytics():
    return analytics.get_analytics()
