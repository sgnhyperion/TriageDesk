"""
LangGraph supervisor graph tests. Owner: Member A.

Exercises the REAL compiled StateGraph with an in-memory checkpointer and an
injected deterministic decider — proving the interrupt()/resume HITL mechanics
without a Gemini key or a database. Skipped if langgraph isn't installed.

Run from repo root:  pytest backend/tests -q
"""
import pytest

pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from contracts.schemas import (  # noqa: E402
    Classification,
    Decision,
    HumanAction,
    RouteDecision,
    Sentiment,
    Severity,
    SupportState,
    TicketCategory,
    ToolName,
)
from backend import graph as g  # noqa: E402


def _state(**kw) -> SupportState:
    base = dict(ticket_id="TCK-GRAPH", ticket_subject="Charged twice",
                ticket_body="billed twice", customer_id="CUST-1",
                classification=Classification(
                    category=TicketCategory.BILLING, severity=Severity.HIGH,
                    sentiment=Sentiment.NEGATIVE, confidence=0.9, in_scope=True, summary="x"))
    base.update(kw)
    return SupportState(**base)


def _decider(*tools: ToolName):
    seq = list(tools)

    def decide(state: SupportState) -> Decision:
        i = state.step_count
        tool = seq[i] if i < len(seq) else ToolName.FINISH
        return Decision(next_tool=tool, args={}, reason=f"{tool.value}")

    return decide


def _graph(*tools: ToolName):
    return g.build_graph(decide=_decider(*tools), checkpointer=MemorySaver())


def test_graph_interrupts_before_high_impact_then_resumes_to_done():
    graph = _graph(ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY, ToolName.SEND_EMAIL)
    state = _state()

    paused = g.start_run(graph, state)
    # Paused at the HITL gate, nothing sent yet.
    assert paused.route == RouteDecision.AWAIT_HUMAN
    assert paused.awaiting_action == ToolName.SEND_EMAIL
    assert paused.final_reply is None
    assert [r.tool for r in paused.scratchpad] == [ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY]
    # The graph genuinely paused: a task is pending on the high_impact node.
    assert graph.get_state(g._config("TCK-GRAPH")).next == ("high_impact",)

    done = g.submit_decision(graph, "TCK-GRAPH", HumanAction.APPROVE)
    assert done.route == RouteDecision.DONE
    assert done.final_reply is not None
    assert ToolName.SEND_EMAIL in [r.tool for r in done.scratchpad]


def test_graph_resume_reject_escalates():
    graph = _graph(ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY, ToolName.SEND_EMAIL)
    g.start_run(graph, _state())
    out = g.submit_decision(graph, "TCK-GRAPH", HumanAction.REJECT)
    assert out.route == RouteDecision.ESCALATE
    assert out.final_reply is None


def test_graph_edit_approve_uses_edited_body():
    graph = _graph(ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY, ToolName.SEND_EMAIL)
    g.start_run(graph, _state())
    out = g.submit_decision(graph, "TCK-GRAPH", HumanAction.EDIT_APPROVE,
                            edited_reply="edited by human")
    assert out.final_reply == "edited by human"
    assert out.route == RouteDecision.DONE


def test_reasoned_trace_pairs_reason_and_args_with_results():
    graph = _graph(ToolName.RETRIEVE_KB, ToolName.DRAFT_REPLY, ToolName.SEND_EMAIL)
    g.start_run(graph, _state())

    trace = g.reasoned_trace(graph, "TCK-GRAPH")
    tools = [s["tool"] for s in trace]
    assert tools == ["retrieve_kb", "draft_reply", "send_email"]   # incl. pending high-impact
    assert all(s["reason"] for s in trace)                         # every step carries a reason
    assert trace[-1]["result"] == {"status": "awaiting_human_approval"}

    # After approval the pending step resolves to a real result.
    g.submit_decision(graph, "TCK-GRAPH", HumanAction.APPROVE)
    resolved = g.reasoned_trace(graph, "TCK-GRAPH")
    assert resolved[-1]["tool"] == "send_email"
    assert resolved[-1]["result"] != {"status": "awaiting_human_approval"}


def test_graph_out_of_scope_refuses_at_start():
    cls = Classification(category=TicketCategory.OUT_OF_SCOPE, severity=Severity.LOW,
                         sentiment=Sentiment.NEUTRAL, confidence=0.9, in_scope=False, summary="x")
    graph = _graph(ToolName.RETRIEVE_KB)
    out = g.start_run(graph, _state(classification=cls))
    assert out.route == RouteDecision.REFUSE
    assert out.scratchpad == []
