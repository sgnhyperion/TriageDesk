"""
The supervisor "brain" loop. Owner: Member A.

⚠️ THIS IS A STUB so the skeleton runs end-to-end WITHOUT a Gemini key.
The fake rule-based decider below must be REPLACED with a Gemini-driven loop:
  decision = get_llm().with_structured_output(Decision).invoke(prompt(state))
plus guardrails (step budget, allow-list, confidence/severity escalation,
validate-and-retry-once on malformed output).
"""
from contracts.schemas import (
    Decision,
    HumanAction,
    RouteDecision,
    SupportState,
    ToolName,
    HIGH_IMPACT_TOOLS,
)
from backend.tools.registry import dispatch


def _fake_decide(state: SupportState) -> Decision:
    """TODO(Member A): replace with a real Gemini structured-output call."""
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


def run(state: SupportState) -> SupportState:
    """Run the brain loop until done / escalate / human approval / step budget."""
    while state.step_count < state.max_steps:
        state.step_count += 1
        decision = _fake_decide(state)          # TODO(Member A): real brain
        state.decision = decision
        tool = decision.next_tool

        if tool == ToolName.FINISH:
            state.route = RouteDecision.DONE
            if state.draft and not state.final_reply:
                state.final_reply = state.draft.body
            return state
        if tool == ToolName.ESCALATE:
            state.route, state.escalated = RouteDecision.ESCALATE, True
            return state
        if tool in HIGH_IMPACT_TOOLS and state.human_decision is None:
            state.route = RouteDecision.AWAIT_HUMAN
            state.awaiting_action = tool         # pause for HITL
            return state

        state.scratchpad.append(dispatch(tool, decision.args, state))

    # step budget exhausted -> escalate (guardrail)
    state.route, state.escalated = RouteDecision.ESCALATE, True
    state.audit_log.append("step budget exceeded -> escalated")
    return state


def resume(state: SupportState, action: HumanAction, edited_reply: str | None = None) -> SupportState:
    """Resume after a human decision. TODO(Member A): replace with real checkpointer resume."""
    state.human_decision = action
    awaited = state.awaiting_action
    state.awaiting_action = None

    if action in (HumanAction.REJECT, HumanAction.ESCALATE):
        state.route, state.escalated = RouteDecision.ESCALATE, True
        state.audit_log.append(f"human {action.value} on {awaited}")
        return state

    # Approved -> execute the awaited high-impact action
    if awaited == ToolName.SEND_EMAIL:
        body = edited_reply or (state.draft.body if state.draft else "")
        state.scratchpad.append(dispatch(ToolName.SEND_EMAIL, {"body": body}, state))
        state.final_reply = body
        state.route = RouteDecision.DONE
    elif awaited == ToolName.PROCESS_REFUND:
        state.scratchpad.append(dispatch(ToolName.PROCESS_REFUND, {}, state))
        state.human_decision = None  # let the loop continue to draft/send
        return run(state)

    state.audit_log.append(f"human {action.value} on {awaited}")
    return state
