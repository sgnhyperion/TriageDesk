"""Real outbound email via Resend. Owner: Member B. HIGH-IMPACT / HITL (runs after approval)."""
import os

from contracts.schemas import SupportState, ToolName, ToolResult


def send_email(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): send via Resend, then write a `messages` (outbound) + audit_log row.

        import resend
        resend.api_key = os.environ["RESEND_API_KEY"]
        resend.Emails.send({"from": os.environ["RESEND_FROM"],
                            "to": [customer_email], "subject": ..., "html": body})

    Stub just records the intent so the flow is demoable without a key.
    """
    body = args.get("body", state.draft.body if state.draft else "")
    state.audit_log.append("send_email (stub) — would send via Resend")
    return ToolResult(tool=ToolName.SEND_EMAIL, ok=True,
                      output={"stub": True, "sent": False, "preview": body[:80]})
