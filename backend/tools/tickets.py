"""Past-ticket search + bug report tools. Owner: Member B.

- search_past_tickets: full-text search over RESOLVED tickets so the brain can
  reuse prior resolutions (e.g. a known PDF-export crash) instead of re-solving
  or filing a duplicate bug.
- create_bug_report: files a new row in bug_reports when no prior resolution
  exists (the "unknown bug" path).
"""
from __future__ import annotations

from contracts.schemas import SupportState, ToolName, ToolResult
from backend.db import queries


def search_past_tickets(args: dict, state: SupportState) -> ToolResult:
    """Find previously RESOLVED tickets similar to this one (Postgres FTS).

    Ranks by ts_rank over subject+body; excludes the current ticket. An empty
    result is a meaningful signal: no prior fix → the brain may file a bug.
    """
    query_text = args.get("query") or f"{state.ticket_subject} {state.ticket_body}"
    limit = int(args.get("limit", 3))

    # plainto_tsquery ANDs every lexeme, which is too strict for free-text tickets
    # (one noise word kills the match). Rewrite it to OR semantics so we match on
    # ANY shared term and let ts_rank surface the most relevant prior ticket.
    or_query = "replace(plainto_tsquery('english', %s)::text, '&', '|')::tsquery"
    matches = queries.fetch_all(
        "select id, subject, category, severity, final_reply, "
        f"       ts_rank(to_tsvector('english', subject || ' ' || body), {or_query}) as rank "
        "from tickets "
        "where status = 'resolved' and id <> %s "
        f"  and to_tsvector('english', subject || ' ' || body) @@ {or_query} "
        "order by rank desc "
        "limit %s",
        (query_text, state.ticket_id, query_text, limit))

    return ToolResult(tool=ToolName.SEARCH_PAST_TICKETS, ok=True, output=queries.jsonable({
        "query": query_text,
        "matches": matches,
        "match_count": len(matches),
        "has_match": bool(matches),
    }))


def create_bug_report(args: dict, state: SupportState) -> ToolResult:
    """Insert a bug_reports row (the 'unknown bug' path).

    Links to the current ticket only if it exists in the DB (FK-safe via the
    subquery, which yields NULL otherwise).
    """
    title = args.get("title") or state.ticket_subject
    description = args.get("description") or state.ticket_body
    severity = args.get("severity")
    if not severity and state.classification:
        severity = state.classification.severity.value
    severity = severity or "medium"

    row = queries.execute(
        "insert into bug_reports (ticket_id, title, description, severity) "
        "values ((select id from tickets where id = %s), %s, %s, %s) "
        "returning id, status",
        (state.ticket_id, title, description, severity))

    return ToolResult(tool=ToolName.CREATE_BUG_REPORT, ok=True, output=queries.jsonable({
        "bug_id": row["id"],
        "status": row["status"],
        "title": title,
        "severity": severity,
    }))
