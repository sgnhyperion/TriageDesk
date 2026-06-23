"""Refund tool (MOCKED — no real payment provider). Owner: Member B. HIGH-IMPACT / HITL."""
from contracts.schemas import SupportState, ToolName, ToolResult


def process_refund(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): insert a row into `refunds` (status='processed') + write audit_log.

    This only runs AFTER human approval (the brain pauses before it).
    """
    state.audit_log.append("process_refund (mock) executed")
    return ToolResult(tool=ToolName.PROCESS_REFUND, ok=True,
                      output={"stub": True, "refund_id": "REF-STUB", "status": "processed_mock"})
