"""QA / policy / guardrail agent — checks a draft before HITL. Owner: Member A."""
from contracts.schemas import DraftReply, GuardrailResult, SupportState


def review(draft: DraftReply, state: SupportState) -> GuardrailResult:
    """TODO(Member A): real checks — PII detection + redaction, policy violations
    (e.g. no refund promised without the refund tool), hallucination vs. retrieved chunks.

    Stub passes everything.
    """
    return GuardrailResult(
        passed=True,
        pii_detected=False,
        policy_violations=[],
        hallucination_risk=False,
        notes="STUB — Member A implements real guardrail checks.",
    )
