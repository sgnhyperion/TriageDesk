"""Resolution agent — drafts the customer reply. Owner: Member A."""
from contracts.schemas import DraftReply, SupportState, ToolName

from backend import llm, prompts


def generate_draft(state: SupportState) -> DraftReply:
    """Draft a grounded reply citing retrieved chunks / looked-up data.

    Real Gemini when a key is configured; degrades to a placeholder draft when no
    key is set or the LLM errors (quota/503), keeping the HITL flow demonstrable.
    """
    def _stub() -> DraftReply:
        return DraftReply(
            body=f"Hi! Thanks for reaching out about \"{state.ticket_subject}\". "
                 f"[STUB DRAFT — replaced by a grounded Gemini reply once a key is set.]",
            cited_chunk_ids=[],
            proposed_actions=[ToolName.SEND_EMAIL],
        )

    return llm.structured_or(DraftReply, prompts.draft_messages(state), _stub)
