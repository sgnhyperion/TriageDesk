"""Resolution agent — drafts the customer reply. Owner: Member A."""
from contracts.schemas import DraftReply, SupportState, ToolName


def generate_draft(state: SupportState) -> DraftReply:
    """TODO(Member A): call get_llm() to write a grounded reply citing retrieved chunks.

    Stub returns a placeholder draft so the HITL flow is demonstrable.
    """
    return DraftReply(
        body=f"Hi! Thanks for reaching out about \"{state.ticket_subject}\". "
             f"[STUB DRAFT — Member A will generate a grounded reply here.]",
        cited_chunk_ids=[],
        proposed_actions=[ToolName.SEND_EMAIL],
    )
