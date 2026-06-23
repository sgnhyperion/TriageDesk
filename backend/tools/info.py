"""request_more_info tool — records a clarifying question, then the ticket waits
for a customer reply. Owner: Member B.

Not high-impact (no approval needed): it just persists the question we want to
ask as an outbound message so the UI can show it and the conversation has a
record. The actual pause/loop routing is the brain's job (Member A).
"""
from __future__ import annotations

from contracts.schemas import SupportState, ToolName, ToolResult
from backend.db import queries

_DEFAULT_QUESTION = "Could you share a bit more detail (what you were doing, any error message) so we can help?"


def request_more_info(args: dict, state: SupportState) -> ToolResult:
    question = args.get("question") or _DEFAULT_QUESTION

    # Persist only if the ticket exists (messages.ticket_id is NOT NULL).
    persisted = False
    if queries.fetch_one("select 1 as x from tickets where id = %s", (state.ticket_id,)):
        queries.execute(
            "insert into messages (ticket_id, direction, sender, body) "
            "values (%s, 'outbound', 'system', %s)",
            (state.ticket_id, question))
        persisted = True

    state.audit_log.append(f"request_more_info: asked '{question[:60]}'")
    return ToolResult(tool=ToolName.REQUEST_MORE_INFO, ok=True, output={
        "question": question,
        "persisted": persisted,
        "awaiting_reply": True,
    })
