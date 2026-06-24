"""Real outbound email. Owner: Member B. HIGH-IMPACT / HITL (after approval).

Provider-switchable via EMAIL_PROVIDER (resend | sendgrid):
  * resend   — needs a verified domain to email arbitrary addresses (the shared
               onboarding@resend.dev sender only reaches your own account email).
  * sendgrid — "Single Sender Verification" lets you verify ONE from-address and
               then email ANY recipient with no domain (handy for demos).

Key-guarded: with the provider's key set it sends for real; otherwise it records
the intent so the flow stays demoable. Either way it writes an outbound `messages`
row + an `audit_log` entry, so the UI/audit trail show "we sent this" regardless.
"""
from __future__ import annotations

import os
import re

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


def _send_resend(to: str | None, subject: str, body: str) -> tuple[bool, str | None, str | None]:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return False, None, "RESEND_API_KEY not set — recorded intent only (no real send)"
    if not to:
        return False, None, "no recipient email resolved"
    try:
        import resend
        resend.api_key = api_key
        resp = resend.Emails.send({
            "from": os.getenv("RESEND_FROM", "TriageDesk <onboarding@resend.dev>"),
            "to": [to], "subject": subject, "html": f"<div>{body}</div>",
        })
        mid = resp.get("id") if isinstance(resp, dict) else getattr(resp, "id", None)
        return True, mid, None
    except Exception as exc:  # never crash the brain on a send failure
        return False, None, str(exc)


def _send_sendgrid(to: str | None, subject: str, body: str) -> tuple[bool, str | None, str | None]:
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        return False, None, "SENDGRID_API_KEY not set — recorded intent only (no real send)"
    if not to:
        return False, None, "no recipient email resolved"
    # SendGrid wants a bare from-address; accept "Name <email>" or "email".
    raw_from = os.getenv("SENDGRID_FROM") or os.getenv("RESEND_FROM", "onboarding@resend.dev")
    m = re.search(r"<([^>]+)>", raw_from)
    from_email = m.group(1) if m else raw_from.strip()
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        message = Mail(from_email=from_email, to_emails=to, subject=subject,
                       html_content=f"<div>{body}</div>")
        resp = sendgrid.SendGridAPIClient(api_key).send(message)
        ok = 200 <= resp.status_code < 300
        mid = resp.headers.get("X-Message-Id") if getattr(resp, "headers", None) else None
        return ok, mid, None if ok else f"sendgrid returned status {resp.status_code}"
    except Exception as exc:  # never crash the brain on a send failure
        return False, None, str(exc)


def _send_via_provider(to: str | None, subject: str, body: str) -> tuple[bool, str | None, str | None]:
    """Dispatch to the configured EMAIL_PROVIDER (resend | sendgrid)."""
    if (os.getenv("EMAIL_PROVIDER") or "resend").strip().lower() == "sendgrid":
        return _send_sendgrid(to, subject, body)
    return _send_resend(to, subject, body)


def send_email(args: dict, state: SupportState) -> ToolResult:
    to = _recipient(args, state)
    subject = args.get("subject") or f"Re: {state.ticket_subject}"
    body = _body(args, state)

    sent, provider_message_id, error = _send_via_provider(to, subject, body)

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
