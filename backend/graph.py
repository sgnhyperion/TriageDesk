"""
LangGraph wiring for the supervisor brain. Owner: Member A.

This is the real `StateGraph` form of the loop in supervisor.py. The plain-Python
loop there remains the reference behavior (and the tested fallback the API uses
today); this module turns it into a graph so HITL works as a true
`interrupt()`/resume across HTTP requests, persisted by a checkpointer.

Topology:

    START → supervisor ─┬─(continue)→ tools ──────→ supervisor   (loop)
                        ├─(await_human)→ high_impact             (interrupt!)
                        └─(done/escalate/refuse)→ END
            high_impact ─┬─(refund approved)→ supervisor          (loop continues)
                         └─(sent / rejected)→ END

The brain's decision policy and every guardrail are reused from supervisor.py so
there is a single source of truth — this module only adds graph structure + the
real interrupt/resume mechanics.

langgraph is imported lazily (inside functions) so the rest of the backend still
imports when the optional dependency is absent.
"""
from typing import Optional

from contracts.schemas import (
    HumanAction,
    RouteDecision,
    SupportState,
    ToolName,
    HIGH_IMPACT_TOOLS,
)
from backend import supervisor
from backend.checkpointer import get_checkpointer
from backend.tools.registry import dispatch

_TERMINAL = {RouteDecision.DONE, RouteDecision.ESCALATE, RouteDecision.REFUSE}


def _changes(state: SupportState, *fields: str) -> dict:
    """Return only the channels a node changed (typed values, not dumps)."""
    return {f: getattr(state, f) for f in fields}


# ─────────────────────────────────────────────────────────────────────────────
# Nodes
# ─────────────────────────────────────────────────────────────────────────────
def _make_supervisor_node(decide: Optional[supervisor.DeciderFn] = None):
    def supervisor_node(state: SupportState) -> dict:
        decider = decide or supervisor._default_decider()

        # Pre-flight scope/confidence/severity guardrail, once at the start.
        if state.step_count == 0 and state.classification is not None:
            if supervisor._scope_guardrail(state) is not None:
                return _changes(state, "route", "refusal_reason", "escalated", "audit_log")

        # Step-budget guardrail.
        if state.step_count >= state.max_steps:
            state.route, state.escalated = RouteDecision.ESCALATE, True
            state.audit_log.append("step budget exceeded -> escalated")
            return _changes(state, "route", "escalated", "audit_log")

        decision = decider(state)
        state.decision = decision
        state.step_count += 1
        tool = decision.next_tool

        if tool == ToolName.FINISH:
            state.route = RouteDecision.DONE
            if state.draft and not state.final_reply:
                state.final_reply = state.draft.body
        elif tool == ToolName.ESCALATE:
            state.route, state.escalated = RouteDecision.ESCALATE, True
            state.audit_log.append(f"brain escalated: {decision.reason}")
        elif tool in HIGH_IMPACT_TOOLS:
            state.route = RouteDecision.AWAIT_HUMAN
            state.awaiting_action = tool
        else:
            state.route = RouteDecision.CONTINUE

        return _changes(state, "decision", "step_count", "route",
                        "awaiting_action", "escalated", "final_reply", "audit_log")

    return supervisor_node


def _tools_node(state: SupportState) -> dict:
    decision = state.decision
    state.scratchpad.append(dispatch(decision.next_tool, decision.args, state))
    if decision.next_tool == ToolName.DRAFT_REPLY:
        supervisor._run_qa(state)  # may set route=ESCALATE / redact the draft
    return _changes(state, "scratchpad", "draft", "guardrail_result",
                    "route", "escalated", "audit_log")


def _high_impact_node(state: SupportState) -> dict:
    """Pause for human approval, then execute (or escalate) the high-impact action."""
    from langgraph.types import interrupt

    awaited = state.awaiting_action

    # Pause: the graph persists here and returns to the caller. On resume,
    # interrupt() returns the payload passed via Command(resume=...).
    payload = interrupt({
        "awaiting_action": awaited.value if awaited else None,
        "draft": state.draft.model_dump() if state.draft else None,
        "guardrail_result": state.guardrail_result.model_dump() if state.guardrail_result else None,
    })

    action = HumanAction(payload["action"])
    edited_reply = payload.get("edited_reply")
    state.human_decision = action
    state.awaiting_action = None

    if action in (HumanAction.REJECT, HumanAction.ESCALATE):
        state.route, state.escalated = RouteDecision.ESCALATE, True
        state.audit_log.append(f"human {action.value} on {awaited}")
    elif awaited == ToolName.SEND_EMAIL:
        body = edited_reply or (state.draft.body if state.draft else "")
        if edited_reply and state.draft:
            state.draft.body = body
        state.scratchpad.append(dispatch(ToolName.SEND_EMAIL, {"body": body}, state))
        state.final_reply = body
        state.route = RouteDecision.DONE
        state.audit_log.append(f"human {action.value} on {awaited}")
    elif awaited == ToolName.PROCESS_REFUND:
        state.scratchpad.append(dispatch(ToolName.PROCESS_REFUND, {}, state))
        state.audit_log.append(f"human {action.value} on {awaited}")
        state.human_decision = None       # let the loop continue (draft -> send)
        state.route = RouteDecision.CONTINUE

    return _changes(state, "scratchpad", "draft", "final_reply", "route",
                    "escalated", "awaiting_action", "human_decision", "audit_log")


# ─────────────────────────────────────────────────────────────────────────────
# Edges
# ─────────────────────────────────────────────────────────────────────────────
def _route_from_supervisor(state: SupportState) -> str:
    if state.route == RouteDecision.CONTINUE:
        return "tools"
    if state.route == RouteDecision.AWAIT_HUMAN:
        return "high_impact"
    return "end"


def _route_from_tools(state: SupportState) -> str:
    return "end" if state.route in _TERMINAL else "supervisor"


def _route_from_high_impact(state: SupportState) -> str:
    return "supervisor" if state.route == RouteDecision.CONTINUE else "end"


# ─────────────────────────────────────────────────────────────────────────────
# Build / compile
# ─────────────────────────────────────────────────────────────────────────────
def graph_available() -> bool:
    """True when langgraph is importable, so the API can prefer the real graph."""
    try:
        import langgraph  # noqa: F401
        return True
    except Exception:
        return False


def build_graph(decide: Optional[supervisor.DeciderFn] = None, checkpointer=None):
    """Compile the supervisor StateGraph. Pass a checkpointer for HITL persistence."""
    from langgraph.graph import StateGraph, START, END

    builder = StateGraph(SupportState)
    builder.add_node("supervisor", _make_supervisor_node(decide))
    builder.add_node("tools", _tools_node)
    builder.add_node("high_impact", _high_impact_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor", _route_from_supervisor,
        {"tools": "tools", "high_impact": "high_impact", "end": END},
    )
    builder.add_conditional_edges(
        "tools", _route_from_tools, {"supervisor": "supervisor", "end": END},
    )
    builder.add_conditional_edges(
        "high_impact", _route_from_high_impact, {"supervisor": "supervisor", "end": END},
    )
    return builder.compile(checkpointer=checkpointer)


# A process-wide compiled graph using the configured checkpointer, so a run and
# its later HITL resume (separate HTTP requests) share persisted state.
_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph(checkpointer=get_checkpointer())
    return _GRAPH


def _config(ticket_id: str) -> dict:
    return {"configurable": {"thread_id": ticket_id}}


def _run_config(ticket_id: str) -> dict:
    """Config for invoke(): thread_id for the checkpointer + LangSmith trace metadata."""
    return {
        "configurable": {"thread_id": ticket_id},
        "run_name": f"ticket:{ticket_id}",
        "tags": ["triagedesk", "supervisor"],
        "metadata": {"ticket_id": ticket_id},
    }


def read_state(graph, ticket_id: str) -> SupportState:
    values = graph.get_state(_config(ticket_id)).values
    return values if isinstance(values, SupportState) else SupportState.model_validate(values)


def _decision_fields(decision) -> tuple:
    """(tool_value, reason, args) from a Decision (object or serialized dict)."""
    if decision is None:
        return None, "", {}
    if isinstance(decision, dict):
        tool = decision.get("next_tool")
        reason, args = decision.get("reason", ""), decision.get("args") or {}
    else:
        tool, reason, args = decision.next_tool, decision.reason, decision.args
    return (tool.value if hasattr(tool, "value") else tool), reason, args


def _result_fields(result) -> tuple:
    """(tool_value, output, ok) from a ToolResult (object or serialized dict)."""
    if isinstance(result, dict):
        tool, out, ok = result.get("tool"), result.get("output") or {}, result.get("ok", True)
    else:
        tool, out, ok = result.tool, result.output, result.ok
    return (tool.value if hasattr(tool, "value") else tool), out, ok


def reasoned_trace(graph, ticket_id: str) -> list[dict]:
    """Reconstruct the UI reasoning trace (TraceStep[]) from the checkpoint history.

    The frozen ToolResult doesn't carry the brain's reason/args, but each tool
    result was caused by the Decision in the preceding checkpoint. We walk the
    history chronologically and attribute every newly-appended scratchpad result
    to the decision that produced it, then add the pending high-impact step if the
    run is paused awaiting approval.
    """
    snaps = list(graph.get_state_history(_config(ticket_id)))
    if not snaps:
        return []

    steps: list[dict] = []
    prev_len = 0
    prev_decision = None
    for snap in reversed(snaps):  # oldest -> newest
        vals = snap.values if isinstance(snap.values, dict) else {}
        scratchpad = vals.get("scratchpad") or []
        while len(scratchpad) > prev_len:                       # a result was appended
            tool_v, reason, args = _decision_fields(prev_decision)
            r_tool, out, ok = _result_fields(scratchpad[prev_len])
            steps.append({"step": len(steps) + 1, "tool": tool_v or r_tool,
                          "reason": reason, "args": args, "result": out, "ok": ok})
            prev_len += 1
        if vals.get("decision") is not None:
            prev_decision = vals["decision"]

    last = next(iter(snaps))  # newest
    lvals = last.values if isinstance(last.values, dict) else {}
    if last.next and "high_impact" in last.next and lvals.get("decision") is not None:
        tool_v, reason, args = _decision_fields(lvals["decision"])
        steps.append({"step": len(steps) + 1, "tool": tool_v, "reason": reason,
                      "args": args, "result": {"status": "awaiting_human_approval"}, "ok": True})
    return steps


def start_run(graph, state: SupportState) -> SupportState:
    """Begin a ticket run; returns the state where it settled (may be awaiting HITL)."""
    graph.invoke(state, _run_config(state.ticket_id))
    return read_state(graph, state.ticket_id)


def submit_decision(graph, ticket_id: str, action: HumanAction,
                    edited_reply: str | None = None) -> SupportState:
    """Resume a paused run with a human decision."""
    from langgraph.types import Command

    graph.invoke(
        Command(resume={"action": action.value, "edited_reply": edited_reply}),
        _run_config(ticket_id),
    )
    return read_state(graph, ticket_id)
