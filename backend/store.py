"""
Ticket + state store — now Postgres-backed. Owner: Member B.

The API layer (Member A) calls only the functions here, so swapping the backing
store from the old in-memory stub to real Postgres is localized to this file —
the routes are unchanged.

Persistence split:
  • Tickets (list/get/create) and the brain's reasoning trace (agent_traces) are
    persisted to Postgres, so the trace/analytics endpoints reflect durable data.
  • The live SupportState object is also cached in-process for continuity between
    /run and /decision within a session. The authoritative pause/resume mechanism
    is Member A's LangGraph Postgres checkpointer (see note in schema.sql); this
    cache is just the bridge the stubbed loop uses today.
"""
from __future__ import annotations

from psycopg.types.json import Json

from contracts.schemas import RouteDecision, SupportState
from backend.db import queries

_TICKET_COLS = "id, customer_id, subject, body, status, category, severity, sentiment, created_at"

# Live in-process SupportState cache (see module docstring).
_STATES: dict[str, SupportState] = {}

# How a run's route maps onto the persisted ticket status.
_ROUTE_TO_STATUS = {
    RouteDecision.DONE: "resolved",
    RouteDecision.ESCALATE: "escalated",
    RouteDecision.REFUSE: "refused",
    RouteDecision.AWAIT_HUMAN: "awaiting_human",
    RouteDecision.CONTINUE: "in_progress",
}


def list_tickets(status: str | None = None) -> list[dict]:
    if status:
        rows = queries.fetch_all(
            f"select {_TICKET_COLS} from tickets where status = %s order by created_at desc",
            (status,))
    else:
        rows = queries.fetch_all(
            f"select {_TICKET_COLS} from tickets order by created_at desc")
    return queries.jsonable(rows)


def get_ticket(ticket_id: str) -> dict | None:
    row = queries.fetch_one(
        f"select {_TICKET_COLS} from tickets where id = %s", (ticket_id,))
    return queries.jsonable(row) if row else None


def create_ticket(subject: str, body: str, customer_email: str | None = None) -> dict:
    # Resolve customer by email if one was supplied.
    customer_id = None
    if customer_email:
        cust = queries.fetch_one("select id from customers where email = %s", (customer_email,))
        customer_id = cust["id"] if cust else None

    # Next TCK-<n> id, continuing the existing numbering.
    nxt = queries.fetch_one(
        "select coalesce(max((substring(id from 5))::int), 1000) as mx "
        "from tickets where id ~ '^TCK-[0-9]+$'")
    new_id = f"TCK-{nxt['mx'] + 1}"

    row = queries.execute(
        f"insert into tickets (id, customer_id, subject, body, status) "
        f"values (%s, %s, %s, %s, 'open') returning {_TICKET_COLS}",
        (new_id, customer_id, subject, body))
    return queries.jsonable(row)


def new_state(ticket: dict) -> SupportState:
    state = SupportState(ticket_id=ticket["id"], ticket_subject=ticket["subject"],
                         ticket_body=ticket["body"], customer_id=ticket.get("customer_id"))
    _STATES[ticket["id"]] = state
    return state


def get_state(ticket_id: str) -> SupportState | None:
    return _STATES.get(ticket_id)


def save_state(state: SupportState) -> None:
    """Cache the live state and persist durable facts (ticket row + trace)."""
    _STATES[state.ticket_id] = state

    # Only touch the DB if this ticket actually exists there (FK-safe).
    if not queries.fetch_one("select 1 as x from tickets where id = %s", (state.ticket_id,)):
        return

    cls = state.classification
    status = _ROUTE_TO_STATUS.get(state.route, "in_progress")
    queries.execute(
        "update tickets set status = %s, "
        "  category = coalesce(%s, category), severity = coalesce(%s, severity), "
        "  sentiment = coalesce(%s, sentiment), final_reply = coalesce(%s, final_reply), "
        "  escalated = %s, updated_at = now() where id = %s",
        (status,
         cls.category.value if cls else None,
         cls.severity.value if cls else None,
         cls.sentiment.value if cls else None,
         state.final_reply,
         state.escalated or state.route == RouteDecision.ESCALATE,
         state.ticket_id))

    # Persist the reasoning trace (rebuild from the scratchpad).
    queries.execute("delete from agent_traces where ticket_id = %s", (state.ticket_id,))
    for i, result in enumerate(state.scratchpad):
        queries.execute(
            "insert into agent_traces (ticket_id, step, tool, reason, args, result, ok) "
            "values (%s, %s, %s, %s, %s, %s, %s)",
            (state.ticket_id, i + 1, result.tool.value, None,
             Json({}), Json(result.output), result.ok))
