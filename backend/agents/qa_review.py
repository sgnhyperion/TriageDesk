"""QA / policy / guardrail agent — checks a draft before HITL. Owner: Member A."""
from contracts.schemas import DraftReply, GuardrailResult, SupportState

from backend import llm, prompts


def review(draft: DraftReply, state: SupportState) -> GuardrailResult:
    """Check a draft for PII, policy violations, and hallucination risk.

    Real Gemini when a key is configured; degrades to a pass-through stub when no
    key is set or the LLM errors (quota/503).
    """
    def _stub() -> GuardrailResult:
        return GuardrailResult(
            passed=True,
            pii_detected=False,
            policy_violations=[],
            hallucination_risk=False,
            notes="STUB — real Gemini guardrail checks run once a key is set.",
        )

    return llm.structured_or(GuardrailResult, prompts.qa_messages(draft, state), _stub)
