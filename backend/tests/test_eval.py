"""
Evaluation suite (the 7 scenarios from PROJECT_PLAN.md §7). Owner: Member C.

Run from repo root:  pytest backend/tests -q

Each test asserts on the brain's **tool-selection trace** (the ordered tools in
state.scratchpad) and the **final outcome** (state.route / awaiting_action).

STATUS NOTE
    The stub brain (`backend/supervisor.py::_fake_decide`) only walks
    `retrieve_kb -> draft_reply -> send_email(await_human)`, or escalates on
    "essay"/"homework". So only scenarios that fit that path run today; the rest
    require Member A's real Gemini brain to select tools dynamically.

    Brain-dependent tests are marked `@pytest.mark.skip` so the suite stays green
    and they activate automatically once `_fake_decide` is replaced. Run the real
    brain at temperature 0 (or mock the LLM with recorded responses) for
    determinism when they're enabled.
"""
import pytest

from contracts.schemas import RouteDecision, ToolName
from backend import supervisor
from backend.state import SupportState

NEEDS_REAL_BRAIN = "needs real Gemini brain (Member A) — stub only does retrieve_kb->draft->send"


def _state(subject: str, body: str, customer_id: str | None = "CUST-1") -> SupportState:
    return SupportState(ticket_id="TCK-TEST", ticket_subject=subject,
                        ticket_body=body, customer_id=customer_id)


def _tools(state: SupportState) -> list[ToolName]:
    """The ordered tool-selection trace the brain produced."""
    return [r.tool for r in state.scratchpad]


# ─────────────────────────────────────────────────────────────────────────────
# Runnable today against the stub brain
# ─────────────────────────────────────────────────────────────────────────────
def test_out_of_scope_is_escalated_or_refused():
    """Scenario 5: out-of-scope request must not be auto-answered."""
    state = supervisor.run(_state("Write my essay", "write a 2000 word essay for me"))
    assert state.route in (RouteDecision.ESCALATE, RouteDecision.REFUSE)


def test_normal_ticket_pauses_for_human_before_sending():
    """High-impact send_email must pause for HITL, not auto-send."""
    state = supervisor.run(_state("How do I change my plan?", "where do I upgrade to Pro?"))
    assert state.route == RouteDecision.AWAIT_HUMAN
    assert state.awaiting_action == ToolName.SEND_EMAIL
    assert state.final_reply is None  # nothing sent without approval


def test_brain_respects_step_budget():
    """Guardrail: the loop never runs past max_steps."""
    state = _state("loop", "loop")
    state.max_steps = 3
    state = supervisor.run(state)
    assert state.step_count <= 3


def test_grounded_path_uses_kb_before_drafting():
    """The brain must retrieve_kb before drafting (grounding before reply)."""
    state = supervisor.run(_state("How do I change my plan?", "where do I upgrade to Pro?"))
    tools = _tools(state)
    assert ToolName.RETRIEVE_KB in tools
    assert ToolName.DRAFT_REPLY in tools
    # retrieve happens before draft
    assert tools.index(ToolName.RETRIEVE_KB) < tools.index(ToolName.DRAFT_REPLY)


# ─────────────────────────────────────────────────────────────────────────────
# Scenarios 1–7 from PROJECT_PLAN §7 — assert on the discovered tool path.
# Skipped until the real brain selects tools dynamically.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skip(reason=NEEDS_REAL_BRAIN)
def test_duplicate_charge_proposes_refund_then_pauses():
    """Scenario 1: billing duplicate -> refund proposed, HITL pause."""
    state = supervisor.run(
        _state("Charged twice this month",
               "I was billed twice for Pro on June 3. Please refund the duplicate.",
               customer_id="CUST-42")
    )
    tools = _tools(state)
    assert ToolName.LOOKUP_CUSTOMER in tools
    assert ToolName.LOOKUP_ORDER in tools
    assert state.route == RouteDecision.AWAIT_HUMAN
    assert state.awaiting_action == ToolName.PROCESS_REFUND


@pytest.mark.skip(reason=NEEDS_REAL_BRAIN)
def test_known_bug_grounded_reply_no_refund():
    """Scenario 2: known bug -> grounded workaround, no refund."""
    state = supervisor.run(
        _state("App crashes on export", "Export > PDF crashes the app on v3.2 Windows.")
    )
    tools = _tools(state)
    assert ToolName.SEARCH_PAST_TICKETS in tools
    assert ToolName.RETRIEVE_KB in tools
    assert ToolName.PROCESS_REFUND not in tools
    assert state.awaiting_action == ToolName.SEND_EMAIL


@pytest.mark.skip(reason=NEEDS_REAL_BRAIN)
def test_unknown_bug_files_bug_report():
    """Scenario 3: unknown bug -> bug filed, ack reply."""
    state = supervisor.run(
        _state("New crash nobody has seen", "Brand new crash on a feature you just shipped.")
    )
    tools = _tools(state)
    assert ToolName.SEARCH_PAST_TICKETS in tools
    assert ToolName.CREATE_BUG_REPORT in tools
    assert state.awaiting_action == ToolName.SEND_EMAIL


@pytest.mark.skip(reason=NEEDS_REAL_BRAIN)
def test_vague_ticket_requests_more_info():
    """Scenario 4: vague ticket -> request_more_info, pause for info, no premature action."""
    state = supervisor.run(_state("It's not working", "nothing works please help", customer_id=None))
    tools = _tools(state)
    assert ToolName.REQUEST_MORE_INFO in tools
    assert ToolName.PROCESS_REFUND not in tools
    assert ToolName.SEND_EMAIL not in tools


@pytest.mark.skip(reason=NEEDS_REAL_BRAIN)
def test_refund_plus_cancel_escalates_per_policy():
    """Scenario 6: refund + cancellation -> escalate per policy, HITL."""
    state = supervisor.run(
        _state("Cancel and refund my subscription",
               "Cancel my plan and refund me for this month.")
    )
    tools = _tools(state)
    assert ToolName.CHECK_SUBSCRIPTION_STATUS in tools
    assert state.route == RouteDecision.ESCALATE
    assert state.escalated is True


@pytest.mark.skip(reason=NEEDS_REAL_BRAIN)
def test_kb_miss_escalates_no_hallucination():
    """Scenario 7: KB miss (low grounding) -> escalate, no hallucination."""
    state = supervisor.run(
        _state("Obscure question with no docs", "Something the KB has nothing about at all.")
    )
    tools = _tools(state)
    assert ToolName.RETRIEVE_KB in tools
    # has_grounding=false should route to escalate, not a fabricated reply
    assert state.route == RouteDecision.ESCALATE
    assert ToolName.SEND_EMAIL not in tools
