"""
contracts/schemas.py — FROZEN INTERFACE CONTRACT (agree in Hour 1)
====================================================================
TriageDesk — the Pydantic models every agent/tool hands off between each other.

WHY THIS FILE EXISTS
    These are the agreed shapes that let 3 people build in parallel without
    blocking each other. Member A's agents PRODUCE these, Member B's tools
    RETURN these, Member C's UI/eval ASSERT on these.

RULE
    "Frozen" does NOT mean never change. It means: do not change a field name
    or type without announcing it in the team channel first, because someone
    else's code depends on it.

STACK NOTE
    LLM provider = Gemini (via langchain-google-genai). Structured outputs are
    produced with `.with_structured_output(<Model>)`. Because Gemini's schema
    adherence is slightly less strict than some providers, the supervisor loop
    (Member A) should validate the parsed object against these models and
    re-prompt once on failure.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums (closed vocabularies — the brain and router must use exactly these)
# ─────────────────────────────────────────────────────────────────────────────
class TicketCategory(str, Enum):
    BILLING = "billing"
    BUG = "bug"
    HOW_TO = "how_to"
    ACCOUNT = "account"
    REFUND = "refund"
    OUT_OF_SCOPE = "out_of_scope"
    OTHER = "other"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ANGRY = "angry"


class ToolName(str, Enum):
    """The full tool registry the Supervisor brain may select from.

    The brain may ONLY emit a value from this enum. Any other value is rejected
    by the allow-list guardrail and the brain is re-prompted.
    """
    LOOKUP_CUSTOMER = "lookup_customer"
    LOOKUP_ORDER = "lookup_order"
    CHECK_SUBSCRIPTION_STATUS = "check_subscription_status"
    RETRIEVE_KB = "retrieve_kb"            # RAG over pgvector
    SEARCH_PAST_TICKETS = "search_past_tickets"
    CREATE_BUG_REPORT = "create_bug_report"
    REQUEST_MORE_INFO = "request_more_info"  # pauses / loops for customer reply
    PROCESS_REFUND = "process_refund"      # HIGH-IMPACT → mock, requires HITL
    DRAFT_REPLY = "draft_reply"
    SEND_EMAIL = "send_email"              # HIGH-IMPACT → real (Resend), requires HITL
    # control actions
    ESCALATE = "escalate"
    FINISH = "finish"


# Tools that MUST pause for human approval before they execute.
HIGH_IMPACT_TOOLS: set[ToolName] = {ToolName.PROCESS_REFUND, ToolName.SEND_EMAIL}


class RouteDecision(str, Enum):
    CONTINUE = "continue"      # brain keeps working
    AWAIT_HUMAN = "await_human"  # interrupt() for HITL approval
    ESCALATE = "escalate"
    REFUSE = "refuse"          # out-of-scope / guardrail refusal
    DONE = "done"


class HumanAction(str, Enum):
    APPROVE = "approve"
    EDIT_APPROVE = "edit_approve"
    ESCALATE = "escalate"
    APPROVE_REFUND = "approve_refund"
    REJECT = "reject"


# ─────────────────────────────────────────────────────────────────────────────
# Agent handoff models
# ─────────────────────────────────────────────────────────────────────────────
class Classification(BaseModel):
    """Output of the (optional) first triage pass; also re-usable by the brain."""
    category: TicketCategory
    severity: Severity
    sentiment: Sentiment
    confidence: float = Field(ge=0.0, le=1.0, description="0-1 confidence in the classification")
    in_scope: bool = Field(description="False => the brain should REFUSE politely")
    summary: str = Field(description="One-line summary of what the customer wants")


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_title: str
    content: str
    score: float = Field(description="Similarity score from pgvector (higher = closer)")


class RetrievedContext(BaseModel):
    """Returned by the retrieve_kb tool."""
    query: str
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    has_grounding: bool = Field(
        description="False when top score < threshold => brain should NOT hallucinate; escalate."
    )


class ToolCall(BaseModel):
    """One decision-to-execute record: what the brain asked for."""
    tool: ToolName
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(description="Why the brain chose this tool (shown in the UI trace)")


class ToolResult(BaseModel):
    """The outcome of running a ToolCall. Appended to SupportState.scratchpad."""
    tool: ToolName
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict, description="Tool-specific payload")
    error: Optional[str] = None


class Decision(BaseModel):
    """STRUCTURED OUTPUT of the Supervisor brain on every loop step.

    The brain reads SupportState (esp. .scratchpad) and emits exactly one of these.
    """
    next_tool: ToolName
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(description="Human-readable justification, shown in the UI reasoning trace")


class DraftReply(BaseModel):
    """Output of draft_reply — the customer-facing message awaiting approval."""
    body: str
    cited_chunk_ids: list[str] = Field(default_factory=list)
    proposed_actions: list[ToolName] = Field(
        default_factory=list,
        description="High-impact actions the brain wants to take next (e.g. send_email, process_refund)",
    )


class GuardrailResult(BaseModel):
    """Output of the QA/policy check applied to a DraftReply before HITL."""
    passed: bool
    pii_detected: bool = False
    policy_violations: list[str] = Field(default_factory=list)
    hallucination_risk: bool = Field(
        default=False, description="True if draft claims things not supported by retrieved chunks"
    )
    redacted_body: Optional[str] = Field(
        default=None, description="PII-redacted version of the draft, if redaction was applied"
    )
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Shared graph state — the single object passed through the LangGraph supervisor
# ─────────────────────────────────────────────────────────────────────────────
class SupportState(BaseModel):
    """The shared system state. Every node reads it and returns an updated copy.

    `scratchpad` is the brain's working memory: the ordered history of tool
    calls + results, so each Decision is informed by everything done so far.
    """
    # inputs
    ticket_id: str
    ticket_subject: str
    ticket_body: str
    customer_id: Optional[str] = None

    # produced as work progresses
    classification: Optional[Classification] = None
    scratchpad: list[ToolResult] = Field(default_factory=list)
    decision: Optional[Decision] = None
    draft: Optional[DraftReply] = None
    guardrail_result: Optional[GuardrailResult] = None

    # routing / control
    route: RouteDecision = RouteDecision.CONTINUE
    step_count: int = 0
    max_steps: int = 8  # step-budget guardrail

    # human-in-the-loop
    awaiting_action: Optional[ToolName] = Field(
        default=None, description="The high-impact tool paused for approval"
    )
    human_decision: Optional[HumanAction] = None
    edited_reply: Optional[str] = None  # set when human chooses EDIT_APPROVE

    # outcome
    final_reply: Optional[str] = None
    escalated: bool = False
    refusal_reason: Optional[str] = None

    # observability
    audit_log: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: deterministic fixtures for parallel dev (all members import these)
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_STATE = SupportState(
    ticket_id="TCK-1001",
    ticket_subject="Charged twice this month",
    ticket_body="Hi, I was billed twice for my Pro plan on June 3. Please help.",
    customer_id="CUST-42",
)
