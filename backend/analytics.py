"""Dashboard analytics aggregation. Owner: Member B.

Aggregates from the tickets + agent_traces tables. Shape matches the openapi
Analytics schema consumed by Member C's dashboard.
"""
from __future__ import annotations

from backend.db import queries


def get_analytics() -> dict:
    counts = queries.fetch_one(
        "select "
        "  count(*) as total, "
        "  count(*) filter (where status = 'resolved') as resolved, "
        "  count(*) filter (where status = 'escalated' or escalated) as escalated, "
        "  count(*) filter (where status = 'refused') as refused "
        "from tickets")

    total = counts["total"] or 0
    escalated = counts["escalated"] or 0

    # avg number of brain steps (trace rows) per ticket that has a trace
    steps_row = queries.fetch_one(
        "select coalesce(avg(c), 0) as avg_steps "
        "from (select count(*) as c from agent_traces group by ticket_id) s")

    # avg wall-clock resolution time for resolved tickets (NULL if none)
    res_row = queries.fetch_one(
        "select extract(epoch from avg(updated_at - created_at)) as secs "
        "from tickets where status = 'resolved'")

    return {
        "total_tickets": total,
        "resolved": counts["resolved"] or 0,
        "escalated": escalated,
        "refused": counts["refused"] or 0,
        "escalation_rate": round(escalated / total, 4) if total else 0.0,
        "avg_steps_per_ticket": round(float(steps_row["avg_steps"]), 2),
        "avg_resolution_seconds": round(float(res_row["secs"]), 2) if res_row["secs"] is not None else None,
    }
