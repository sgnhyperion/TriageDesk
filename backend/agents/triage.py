"""Triage agent — classifies a ticket. Owner: Member A."""
from contracts.schemas import Classification, Sentiment, Severity, SupportState, TicketCategory


def classify(state: SupportState) -> Classification:
    """TODO(Member A): call get_llm().with_structured_output(Classification).

    Stub returns a neutral classification so the skeleton runs.
    """
    return Classification(
        category=TicketCategory.OTHER,
        severity=Severity.MEDIUM,
        sentiment=Sentiment.NEUTRAL,
        confidence=0.5,
        in_scope=True,
        summary=state.ticket_subject,
    )
