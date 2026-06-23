"""Dashboard analytics aggregation. Owner: Member B."""


def get_analytics() -> dict:
    """TODO(Member B): aggregate from the tickets/audit tables in Supabase.

    Stub returns zeros matching the openapi.yaml Analytics shape.
    """
    return {
        "total_tickets": 0,
        "resolved": 0,
        "escalated": 0,
        "refused": 0,
        "escalation_rate": 0.0,
        "avg_steps_per_ticket": 0.0,
        "avg_resolution_seconds": None,
    }
