"""
The supervisor "brain" loop + guardrails. Owner: Member A.

The brain reads SupportState (especially `.scratchpad`, its working memory),
emits exactly one structured `Decision` per step, runs the chosen tool, appends
the `ToolResult`, and repeats — until finish / refuse / escalate / a high-impact
action that needs human approval / the step budget is hit.

What makes the brain *governed* (deterministic Python around the LLM policy):
  - allow-list   — Decision.next_tool is a ToolName enum, so malformed/invalid
                   tools are rejected at parse time and re-prompted (see llm.structured).
  - step budget  — the loop never runs past state.max_steps; exceeding it escalates.
  - scope/confidence/severity — out-of-scope refuses; low confidence or critical
                   severity escalates, before any tool runs.
  - QA pass      — every freshly produced draft is checked (PII/policy/hallucination);
                   redact if possible, else escalate.
  - HITL         — process_refund / send_email pause for human approval first.

The LLM decider is INJECTABLE (`run(state, decide=...)`) so the loop and every
guardrail are unit-testable with no Gemini key. With a key set, the real brain
(`_llm_decide`) is used automatically; without one, a deterministic rule-based
fallback keeps the skeleton and eval suite runnable.
"""
from typing import Callable, Optional

from contracts.schemas import (
    Decision,
    HumanAction,
    RouteDecision,
    Severity,
    SupportState,
    ToolName,
    HIGH_IMPACT_TOOLS,
)
from backend import llm, prompts
from backend.agents import qa_review
from backend.tools.registry import dispatch

DeciderFn = Callable[[SupportState], Decision]

# Below this classification confidence we don't act on a guess — escalate.
CONFIDENCE_FLOOR = 0.35


# ─────────────────────────────────────────────────────────────────────────────
# The brain's policy: choose the next tool
# ─────────────────────────────────────────────────────────────────────────────
def _llm_decide(state: SupportState) -> Decision:
    """Real Gemini brain: structured-output Decision, validated + retried once.

    Degrades to the deterministic decider if the LLM errors (quota/503), so a run
    never crashes mid-loop on a free-tier rate limit.
    """
    return llm.structured_or(Decision, prompts.supervisor_messages(state),
                             lambda: _fake_decide(state))


def _fake_decide(state: SupportState) -> Decision:
    """Deterministic fallback when no Gemini key is set.

    Keeps the skeleton + eval suite runnable with zero external dependencies.
    """
    done = {r.tool for r in state.scratchpad}
    text = f"{state.ticket_subject} {state.ticket_body}".lower()

    if any(w in text for w in ("essay", "homework")):
        return Decision(next_tool=ToolName.ESCALATE, reason="Request is out of support scope.")
    if ToolName.DRAFT_REPLY in done:
        return Decision(next_tool=ToolName.SEND_EMAIL,
                        reason="Draft is ready; propose sending it (needs human approval).")
    if ToolName.RETRIEVE_KB in done:
        return Decision(next_tool=ToolName.DRAFT_REPLY,
                        reason="We have grounding; draft a reply to the customer.")
    return Decision(next_tool=ToolName.RETRIEVE_KB,
                    args={"query": state.ticket_subject},
                    reason="Find relevant help-center passages to ground the answer.")


def _default_decider() -> DeciderFn:
    return _llm_decide if llm.llm_available() else _fake_decide


# ─────────────────────────────────────────────────────────────────────────────
# Governance: deterministic guardrails around the brain
# ─────────────────────────────────────────────────────────────────────────────
def _scope_guardrail(state: SupportState) -> Optional[SupportState]:
    """Pre-flight check on the classification. Returns a terminal state if it fires."""
    c = state.classification
    if c is None:
        return None
    if not c.in_scope:
        state.route = RouteDecision.REFUSE
        state.refusal_reason = "Request is outside the scope of customer support."
        state.audit_log.append("guardrail: out_of_scope -> refuse")
        return state
    if c.confidence < CONFIDENCE_FLOOR:
        state.route, state.escalated = RouteDecision.ESCALATE, True
        state.audit_log.append(f"guardrail: low confidence {c.confidence:.2f} -> escalate")
        return state
    if c.severity == Severity.CRITICAL:
        state.route, state.escalated = RouteDecision.ESCALATE, True
        state.audit_log.append("guardrail: critical severity -> escalate")
        return state
    return None


def _run_qa(state: SupportState) -> Optional[SupportState]:
    """QA/policy pass on a freshly produced draft. Redact if possible, else escalate."""
    if not state.draft:
        return None
    result = qa_review.review(state.draft, state)
    state.guardrail_result = result
    if result.passed:
        return None
    if result.redacted_body:
        state.draft.body = result.redacted_body
        state.audit_log.append("guardrail: PII redacted in draft")
        return None
    state.route, state.escalated = RouteDecision.ESCALATE, True
    reason = ", ".join(result.policy_violations) or "hallucination risk"
    state.audit_log.append(f"guardrail: QA failed ({reason}) -> escalate")
    return state


# ─────────────────────────────────────────────────────────────────────────────
# The loop
# ─────────────────────────────────────────────────────────────────────────────
def run(state: SupportState, decide: Optional[DeciderFn] = None) -> SupportState:
    """Run the governed brain loop until done / refuse / escalate / await_human / budget."""
    decide = decide or _default_decider()

    stop = _scope_guardrail(state)
    if stop is not None:
        return stop

    while state.step_count < state.max_steps:
        state.step_count += 1
        decision = decide(state)
        state.decision = decision
        tool = decision.next_tool

        if tool == ToolName.FINISH:
            state.route = RouteDecision.DONE
            if state.draft and not state.final_reply:
                state.final_reply = state.draft.body
            return state

        if tool == ToolName.ESCALATE:
            state.route, state.escalated = RouteDecision.ESCALATE, True
            state.audit_log.append(f"brain escalated: {decision.reason}")
            return state

        if tool in HIGH_IMPACT_TOOLS and state.human_decision is None:
            state.route = RouteDecision.AWAIT_HUMAN
            state.awaiting_action = tool  # pause for HITL approval
            return state

        state.scratchpad.append(dispatch(tool, decision.args, state))

        if tool == ToolName.DRAFT_REPLY:
            stop = _run_qa(state)
            if stop is not None:
                return stop

    # step budget exhausted -> escalate (guardrail)
    state.route, state.escalated = RouteDecision.ESCALATE, True
    state.audit_log.append("step budget exceeded -> escalated")
    return state


def resume(
    state: SupportState,
    action: HumanAction,
    edited_reply: str | None = None,
    decide: Optional[DeciderFn] = None,
) -> SupportState:
    """Resume after a human decision on a paused high-impact action.

    TODO(Member A): once the LangGraph Postgres checkpointer (checkpointer.py) is
    wired, this becomes a graph `resume` via interrupt()/Command; the control flow
    below is the reference behavior that graph must reproduce.
    """
    state.human_decision = action
    awaited = state.awaiting_action
    state.awaiting_action = None

    if action in (HumanAction.REJECT, HumanAction.ESCALATE):
        state.route, state.escalated = RouteDecision.ESCALATE, True
        state.audit_log.append(f"human {action.value} on {awaited}")
        return state

    # Approved -> execute the awaited high-impact action.
    if awaited == ToolName.SEND_EMAIL:
        body = edited_reply or (state.draft.body if state.draft else "")
        if edited_reply and state.draft:
            state.draft.body = body
        state.scratchpad.append(dispatch(ToolName.SEND_EMAIL, {"body": body}, state))
        state.final_reply = body
        state.route = RouteDecision.DONE
        state.audit_log.append(f"human {action.value} on {awaited}")
        return state

    if awaited == ToolName.PROCESS_REFUND:
        state.scratchpad.append(dispatch(ToolName.PROCESS_REFUND, {}, state))
        state.audit_log.append(f"human {action.value} on {awaited}")
        state.human_decision = None  # let the loop continue (draft -> send)
        return run(state, decide=decide)

    state.audit_log.append(f"human {action.value} on {awaited}")
    return state
