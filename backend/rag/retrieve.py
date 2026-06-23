"""retrieve_kb tool — RAG over pgvector. Owner: Member B."""
from contracts.schemas import RetrievedContext, SupportState, ToolName, ToolResult

GROUNDING_THRESHOLD = 0.70  # below this, brain should escalate (no hallucination)


def retrieve_kb(args: dict, state: SupportState) -> ToolResult:
    """TODO(Member B): embed args['query'], call the `match_kb_chunks` SQL function,
    build RetrievedContext, set has_grounding = (top score >= GROUNDING_THRESHOLD).

    Stub returns empty grounding.
    """
    ctx = RetrievedContext(query=args.get("query", state.ticket_subject),
                           chunks=[], has_grounding=False)
    return ToolResult(tool=ToolName.RETRIEVE_KB, ok=True,
                      output={"stub": True, "has_grounding": ctx.has_grounding,
                              "chunk_count": len(ctx.chunks)})
