"""Triage agent — classifies a ticket. Owner: Member A."""
from contracts.schemas import Classification, Sentiment, Severity, SupportState, TicketCategory

from backend import llm, prompts


def classify(state: SupportState) -> Classification:
    """Classify the ticket into a structured Classification.

    Real Gemini structured output when a key is configured; degrades to a neutral
    stub when no key is set or the LLM errors (quota/503).
    """
    def _stub() -> Classification:
        return Classification(
            category=TicketCategory.OTHER,
            severity=Severity.MEDIUM,
            sentiment=Sentiment.NEUTRAL,
            confidence=0.5,
            in_scope=True,
            summary=state.ticket_subject,
        )

    return llm.structured_or(Classification, prompts.classification_messages(state), _stub)
