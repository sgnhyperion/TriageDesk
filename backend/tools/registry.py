"""
Tool registry — maps a ToolName to the function that runs it.

This mapping is a small A↔B contract: Member B writes the tool functions
(signature `fn(args: dict, state) -> ToolResult`), Member A's brain dispatches
through here. Add a tool by implementing it and registering it below.
"""
from contracts.schemas import SupportState, ToolName, ToolResult

from backend.tools import crm, info, refund, tickets
from backend.rag import retrieve
from backend.integrations import email_resend
from backend.agents import resolution


def _draft_reply(args: dict, state: SupportState) -> ToolResult:
    """draft_reply is backed by the resolution agent (Member A)."""
    draft = resolution.generate_draft(state)
    state.draft = draft
    return ToolResult(tool=ToolName.DRAFT_REPLY, ok=True, output={"body": draft.body})


# ToolName -> callable(args, state) -> ToolResult
TOOL_REGISTRY = {
    ToolName.LOOKUP_CUSTOMER: crm.lookup_customer,
    ToolName.LOOKUP_ORDER: crm.lookup_order,
    ToolName.CHECK_SUBSCRIPTION_STATUS: crm.check_subscription_status,
    ToolName.SEARCH_PAST_TICKETS: tickets.search_past_tickets,
    ToolName.CREATE_BUG_REPORT: tickets.create_bug_report,
    ToolName.REQUEST_MORE_INFO: info.request_more_info,
    ToolName.PROCESS_REFUND: refund.process_refund,
    ToolName.RETRIEVE_KB: retrieve.retrieve_kb,
    ToolName.DRAFT_REPLY: _draft_reply,
    ToolName.SEND_EMAIL: email_resend.send_email,
}


def dispatch(tool: ToolName, args: dict, state: SupportState) -> ToolResult:
    fn = TOOL_REGISTRY.get(tool)
    if fn is None:
        return ToolResult(tool=tool, ok=False, error=f"No tool registered for {tool}")
    try:
        return fn(args or {}, state)
    except Exception as exc:  # tools must never crash the brain
        return ToolResult(tool=tool, ok=False, error=str(exc))
