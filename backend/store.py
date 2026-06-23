"""
In-memory ticket + state store. STUB so the skeleton runs without Supabase.

TODO(Member B): replace this with real Supabase reads/writes (tickets table,
agent_traces, etc.). The API layer (Member A) calls only the functions here, so
swapping the backing store later is localized.
"""
import json
from pathlib import Path

from contracts.schemas import SupportState

_FIXTURES = Path(__file__).resolve().parents[1] / "contracts" / "fixtures" / "sample_tickets.json"

# ticket_id -> raw ticket dict ; ticket_id -> SupportState
_TICKETS: dict[str, dict] = {}
_STATES: dict[str, SupportState] = {}


def _seed() -> None:
    if _TICKETS:
        return
    for t in json.loads(_FIXTURES.read_text()):
        _TICKETS[t["id"]] = t


def list_tickets(status: str | None = None) -> list[dict]:
    _seed()
    items = list(_TICKETS.values())
    if status:
        items = [t for t in items if t.get("status") == status]
    return items


def get_ticket(ticket_id: str) -> dict | None:
    _seed()
    return _TICKETS.get(ticket_id)


def create_ticket(subject: str, body: str, customer_email: str | None = None) -> dict:
    _seed()
    new_id = f"TCK-{1000 + len(_TICKETS) + 1}"
    ticket = {"id": new_id, "customer_id": None, "subject": subject, "body": body,
              "status": "open", "category": None, "severity": None, "sentiment": None,
              "created_at": "2026-06-23T00:00:00Z"}
    _TICKETS[new_id] = ticket
    return ticket


def new_state(ticket: dict) -> SupportState:
    state = SupportState(ticket_id=ticket["id"], ticket_subject=ticket["subject"],
                         ticket_body=ticket["body"], customer_id=ticket.get("customer_id"))
    _STATES[ticket["id"]] = state
    return state


def get_state(ticket_id: str) -> SupportState | None:
    return _STATES.get(ticket_id)


def save_state(state: SupportState) -> None:
    _STATES[state.ticket_id] = state
