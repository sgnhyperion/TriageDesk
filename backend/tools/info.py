"""request_more_info tool — pauses/loops for a customer reply. Owner: Member B."""
from contracts.schemas import SupportState, ToolName, ToolResult


def request_more_info(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): record the clarifying question; the ticket waits for a reply.

    The question text can come from args['question'] (set by the brain).
    """
    question = args.get("question", "Could you share more details so we can help?")
    return ToolResult(tool=ToolName.REQUEST_MORE_INFO, ok=True,
                      output={"stub": True, "question": question})
