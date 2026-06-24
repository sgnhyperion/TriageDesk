"""
Supervisor brain + guardrail tests. Owner: Member A.

These exercise the governed loop deterministically by INJECTING a decider
(`supervisor.run(state, decide=...)`), so no Gemini key or network is needed.
They assert the governance contract: scope refusal, confidence floor, critical
severity, step budget, the HITL pause, and resume. (Member C's test_eval.py
covers end-to-end scenarios against the rule-based fallback brain.)

Run from repo root:  pytest backend/tests -q
"""
import pytest

from contracts.schemas import (
    Classification,
    Decision,
    GuardrailResult,
    HumanAction,
    RouteDecision,
    Sentiment,
    Severity,
    SupportState,
    TicketCategory,
    ToolName,
)
from backend import supervisor
from backend.agents import qa_review


def _state(**kw) -> SupportState:
    base = dict(ticket_id="TCK-TEST", ticket_subject="subj", ticket_body="body", customer_id="CUST-1")
    base.update(kw)
    return SupportState(**base)


def _classification(**kw) -> Classification:
    base = dict(category=TicketCategory.HOW_TO, severity=Severity.LOW, sentiment=Sentiment.NEUTRAL,
                confidence=0.9, in_scope=True, summary="x")
    base.update(kw)
    return Classification(**base)


def _decider(*tools: ToolName):
    """A decider that emits the given tools in order, then finishes."""
    seq = list(tools)

    def decide(state: SupportState) -> Decision:
        i = state.step_count - 1
        tool = seq[i] if i < len(seq) else ToolName.FINISH
        return Decision(next_tool=tool, args={}, reason=f"step {state.step_count}: {tool.value}")

    return decide


# ── allow-list ──────────────────────────────────────────────────────────────
def test_decision_only_accepts_known_tools():
    """The allow-list is the ToolName enum: an unknown tool can't even be constructed."""
    with pytest.raises(Exception):
        Decision(next_tool="not_a_real_tool", reason="x")


# ── scope / confidence / severity guardrails (pre-flight) ─────────────────────
def test_out_of_scope_refuses_without_running_tools():
    state = _state(classification=_classification(in_scope=False, category=TicketCategory.OUT_OF_SCOPE))
    out = supervisor.run(state, decide=_decider(ToolName.RETRIEVE_KB))
    assert out.route == RouteDecision.REFUSE
    assert out.refusal_reason is not None
    assert out.scratchpad == []          # no tool ran
    assert out.step_count == 0


def test_low_confidence_escalates():
    state = _state(classification=_classification(confidence=0.1))
    out = supervisor.run(state, decide=_decider(ToolName.RETRIEVE_KB))
    assert out.route == RouteDecision.ESCALATE
    assert out.escalated is True
    assert out.scratchpad == []


def test_critical_severity_escalates():
    state = _state(classification=_classification(severity=Severity.CRITICAL))
    out = supervisor.run(state, decide=_decider(ToolName.RETRIEVE_KB))
    assert out.route == RouteDecision.ESCALATE
    assert out.escalated is True


# ── HITL pause ────────────────────────────────────────────────────────────────
def test_high_impact_tool_pauses_for_human():
    state = _state(classification=_classification())
    out = supervisor.run(state, decide=_decider(ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY,
                                                 ToolName.SEND_EMAIL))
    assert out.route == RouteDecision.AWAIT_HUMAN
    assert out.awaiting_action == ToolName.SEND_EMAIL
    assert out.final_reply is None                              # nothing sent yet
    assert [r.tool for r in out.scratchpad] == [ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY]
    assert out.guardrail_result is not None                    # QA ran on the draft


# ── step budget ───────────────────────────────────────────────────────────────
def test_step_budget_exceeded_escalates():
    state = _state(classification=_classification(), max_steps=3)
    # A decider that only ever looks things up never reaches finish.
    out = supervisor.run(state, decide=lambda s: Decision(next_tool=ToolName.LOOKUP_CUSTOMER,
                                                           reason="loop"))
    assert out.step_count == 3
    assert out.route == RouteDecision.ESCALATE
    assert "step budget" in out.audit_log[-1]


# ── QA guardrail on the draft ─────────────────────────────────────────────────
def test_failed_qa_escalates(monkeypatch):
    monkeypatch.setattr(qa_review, "review", lambda draft, state: GuardrailResult(
        passed=False, policy_violations=["promised refund with no refund action"]))
    state = _state(classification=_classification())
    out = supervisor.run(state, decide=_decider(ToolName.DRAFT_REPLY))
    assert out.route == RouteDecision.ESCALATE
    assert out.escalated is True


def test_qa_redaction_keeps_running(monkeypatch):
    monkeypatch.setattr(qa_review, "review", lambda draft, state: GuardrailResult(
        passed=False, pii_detected=True, redacted_body="redacted"))
    state = _state(classification=_classification())
    out = supervisor.run(state, decide=_decider(ToolName.DRAFT_REPLY, ToolName.SEND_EMAIL))
    assert out.draft.body == "redacted"
    assert out.route == RouteDecision.AWAIT_HUMAN     # redacted, then proceeded to send pause


# ── resume after human decision ───────────────────────────────────────────────
def test_resume_approve_sends_and_finishes():
    state = _state(classification=_classification())
    state = supervisor.run(state, decide=_decider(ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY,
                                                   ToolName.SEND_EMAIL))
    assert state.route == RouteDecision.AWAIT_HUMAN
    out = supervisor.resume(state, HumanAction.APPROVE)
    assert out.route == RouteDecision.DONE
    assert out.final_reply is not None
    assert ToolName.SEND_EMAIL in [r.tool for r in out.scratchpad]


def test_resume_reject_escalates():
    state = _state(classification=_classification())
    state = supervisor.run(state, decide=_decider(ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY,
                                                   ToolName.SEND_EMAIL))
    out = supervisor.resume(state, HumanAction.REJECT)
    assert out.route == RouteDecision.ESCALATE
    assert out.final_reply is None


def test_resume_edit_approve_uses_edited_body():
    state = _state(classification=_classification())
    state = supervisor.run(state, decide=_decider(ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY,
                                                   ToolName.SEND_EMAIL))
    out = supervisor.resume(state, HumanAction.EDIT_APPROVE, edited_reply="my edited reply")
    assert out.final_reply == "my edited reply"
    assert out.route == RouteDecision.DONE
