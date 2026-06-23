"""Past-ticket search + bug report tools. Owner: Member B."""
from contracts.schemas import SupportState, ToolName, ToolResult


def search_past_tickets(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): search the `tickets` table (text/similarity) for prior issues."""
    return ToolResult(tool=ToolName.SEARCH_PAST_TICKETS, ok=True,
                      output={"stub": True, "matches": []})


def create_bug_report(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): insert a row into `bug_reports`."""
    return ToolResult(tool=ToolName.CREATE_BUG_REPORT, ok=True,
                      output={"stub": True, "bug_id": "BUG-STUB"})
