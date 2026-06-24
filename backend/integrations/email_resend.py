"""Real outbound email via Resend. Owner: Member B. HIGH-IMPACT / HITL (after approval).

Key-guarded: when RESEND_API_KEY is set it sends for real; otherwise it records
the intent so the whole flow stays demoable without a key. Either way it writes
an outbound `messages` row + an `audit_log` entry, so the UI and audit trail show
"we sent this" regardless. Flip the env var to go live — zero code change.
"""
from __future__ import annotations

import os

from contracts.schemas import SupportState, ToolName, ToolResult
from backend.db import queries


def _recipient(args: dict, state: SupportState) -> str | None:
    if args.get("to"):
        return args["to"]
    if state.customer_id:
        row = queries.fetch_one("select email from customers where id = %s", (state.customer_id,))
        if row:
            return row["email"]
    return None


def _body(args: dict, state: SupportState) -> str:
    # Prefer a human-edited reply, then the brain's draft, then an explicit arg.
    if state.edited_reply:
        return state.edited_reply
    if state.draft and state.draft.body:
        return state.draft.body
    return args.get("body", "")


def send_email(args: dict, state: SupportState) -> ToolResult:
    to = _recipient(args, state)
    subject = args.get("subject") or f"Re: {state.ticket_subject}"
    body = _body(args, state)

    api_key = os.getenv("RESEND_API_KEY")
    sent = False
    provider_message_id = None
    error = None

    if api_key and to:
        try:
            import resend
            resend.api_key = api_key
            resp = resend.Emails.send({
                "from": os.getenv("RESEND_FROM", "TriageDesk <onboarding@resend.dev>"),
                "to": [to],
                "subject": subject,
                "html": f"<div>{body}</div>",
            })
            provider_message_id = resp.get("id") if isinstance(resp, dict) else getattr(resp, "id", None)
            sent = True
        except Exception as exc:  # never crash the brain on a send failure
            error = str(exc)
    elif not api_key:
        error = "RESEND_API_KEY not set — recorded intent only (no real send)"

    # Persist the outbound message (FK-safe: only if the ticket exists).
    if body and queries.fetch_one("select 1 as x from tickets where id = %s", (state.ticket_id,)):
        queries.execute(
            "insert into messages (ticket_id, direction, sender, body) "
            "values (%s, 'outbound', 'agent', %s)",
            (state.ticket_id, body))

    queries.write_audit("send_email", {
        "to": to, "subject": subject, "sent": sent,
        "provider_message_id": provider_message_id, "error": error,
    }, ticket_id=state.ticket_id)
    state.audit_log.append(f"send_email: to={to} sent={sent}")
    if sent:
        state.final_reply = body

    return ToolResult(tool=ToolName.SEND_EMAIL, ok=True, output={
        "sent": sent,
        "to": to,
        "subject": subject,
        "provider_message_id": provider_message_id,
        "mock": not sent,
        "error": error,
        "preview": body[:120],
    })
