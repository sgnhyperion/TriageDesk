"""retrieve_kb tool — RAG over pgvector. Owner: Member B.

Embeds the query with Gemini, runs the match_kb_chunks() similarity function, and
returns a RetrievedContext. The key guardrail: `has_grounding` is False when the
top similarity is below GROUNDING_THRESHOLD — the signal for the brain to escalate
instead of hallucinating an answer the KB doesn't support.
"""
from __future__ import annotations

import os

from contracts.schemas import RetrievedChunk, RetrievedContext, SupportState, ToolName, ToolResult
from backend.db import queries
from backend.rag.embed import embed_query

# Top score below this => no grounding => the brain escalates instead of
# hallucinating. Calibrated for gemini-embedding-001 @768 (relevant queries
# score ~0.64-0.68, unrelated ~0.52); override with the GROUNDING_THRESHOLD env.
GROUNDING_THRESHOLD = float(os.getenv("GROUNDING_THRESHOLD", "0.58"))


def retrieve_kb(args: dict, state: SupportState) -> ToolResult:
    query = args.get("query") or f"{state.ticket_subject} {state.ticket_body}".strip()
    match_count = int(args.get("match_count", 4))

    embedding = embed_query(query)
    rows = queries.fetch_all(
        "select chunk_id, document_title, content, score "
        "from match_kb_chunks(%s::vector, %s)",
        (_vector_literal(embedding), match_count))

    chunks = [
        RetrievedChunk(chunk_id=str(r["chunk_id"]), document_title=r["document_title"],
                       content=r["content"], score=float(r["score"]))
        for r in rows
    ]
    top_score = max((c.score for c in chunks), default=0.0)
    has_grounding = top_score >= GROUNDING_THRESHOLD

    ctx = RetrievedContext(query=query, chunks=chunks, has_grounding=has_grounding)
    output = ctx.model_dump()
    output["top_score"] = top_score
    return ToolResult(tool=ToolName.RETRIEVE_KB, ok=True, output=output)


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"
