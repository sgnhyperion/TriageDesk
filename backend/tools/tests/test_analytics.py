"""Tests for analytics aggregation (Member B). DB only — no Gemini key needed."""
from __future__ import annotations

from backend import analytics


def test_analytics_shape_and_values():
    a = analytics.get_analytics()
    # exact openapi Analytics keys
    assert set(a) == {
        "total_tickets", "resolved", "escalated", "refused",
        "escalation_rate", "avg_steps_per_ticket", "avg_resolution_seconds",
    }
    # seed has 10 tickets, 5 resolved
    assert a["total_tickets"] >= 10
    assert a["resolved"] >= 5
    assert 0.0 <= a["escalation_rate"] <= 1.0
    assert isinstance(a["avg_steps_per_ticket"], float)
    assert a["avg_resolution_seconds"] is None or a["avg_resolution_seconds"] >= 0
