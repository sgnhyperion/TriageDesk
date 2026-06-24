"""
Prompt builders for the supervisor brain and the LLM agents. Owner: Member A.

Each function returns a list of (role, content) message tuples, which langchain
chat models accept directly via `.invoke(...)`. Keeping prompts here (and free of
any langchain import) means the brain/agents stay thin and the wording is easy to
tune in one place.
"""
from contracts.schemas import DraftReply, SupportState, ToolName


def _tool_menu() -> str:
    return "\n".join(f"  - {t.value}" for t in ToolName)


def _scratchpad_digest(state: SupportState) -> str:
    """Render the ordered tool-call history the brain reasons over."""
    if not state.scratchpad:
        return "(no tools run yet)"
    lines = []
    for i, r in enumerate(state.scratchpad, 1):
        status = "ok" if r.ok else f"ERROR: {r.error}"
        lines.append(f"  {i}. {r.tool.value} -> {status}; output={r.output}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Supervisor brain
# ─────────────────────────────────────────────────────────────────────────────
SUPERVISOR_SYSTEM = """You are the supervisor brain of TriageDesk, an AI customer-support desk.
On each turn you choose EXACTLY ONE next tool to make progress on the ticket, based on everything
done so far. You do not write prose to the customer here — you emit a single structured Decision
(next_tool, args, reason).

Available tools:
{tool_menu}

Operating rules:
- Choose the single most useful next step. Do NOT repeat a tool whose result you already have.
- Ground customer-facing claims first: look up real data (customer/order/subscription) and/or
  retrieve_kb before drafting a reply.
- draft_reply BEFORE send_email. Never choose send_email without a draft in hand.
- process_refund and send_email are HIGH-IMPACT: choosing them pauses the run for human approval,
  so only choose them once you genuinely intend that action.
- When a reply has been drafted and the customer-facing action is done/approved, choose finish.
- Choose escalate when: the request needs a human by policy (e.g. a refund tied to a cancellation
  or legal/billing dispute), the knowledge base returned no grounding, or you are stuck.
- `reason` is shown to a human in the UI reasoning trace — keep it a concise, honest justification.
"""


def supervisor_messages(state: SupportState):
    c = state.classification
    cls = (
        f"category={c.category.value}, severity={c.severity.value}, sentiment={c.sentiment.value}, "
        f"confidence={c.confidence:.2f}, in_scope={c.in_scope}, summary={c.summary!r}"
        if c else "(not classified yet)"
    )
    human = f"""TICKET {state.ticket_id}
Subject: {state.ticket_subject}
Body: {state.ticket_body}
Customer: {state.customer_id or "unknown"}
Classification: {cls}

Work so far (scratchpad):
{_scratchpad_digest(state)}

This is step {state.step_count} of at most {state.max_steps}. Choose the next tool."""
    return [
        ("system", SUPERVISOR_SYSTEM.format(tool_menu=_tool_menu())),
        ("human", human),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Triage / classification
# ─────────────────────────────────────────────────────────────────────────────
CLASSIFY_SYSTEM = """You classify an incoming customer-support ticket into a structured Classification.

- category: one of billing, bug, how_to, account, refund, out_of_scope, other.
- in_scope=False ONLY when the request is unrelated to supporting this product (e.g. "write my
  essay", general chit-chat, abuse). Billing, bugs, how-to, account, and refund requests are in scope.
- severity reflects customer/business impact (critical = outage, data loss, legal/financial risk).
- sentiment reflects the customer's tone.
- confidence is your 0-1 confidence in the category.
- summary is one line describing what the customer wants."""


def classification_messages(state: SupportState):
    human = f"Subject: {state.ticket_subject}\nBody: {state.ticket_body}"
    return [("system", CLASSIFY_SYSTEM), ("human", human)]


# ─────────────────────────────────────────────────────────────────────────────
# Resolution / draft reply
# ─────────────────────────────────────────────────────────────────────────────
DRAFT_SYSTEM = """You write a concise, friendly, professional support reply to the customer.

- Ground every factual claim in the retrieved knowledge-base chunks and looked-up data found in
  the scratchpad. Do NOT invent policies, prices, dates, or facts.
- When you rely on a KB chunk, include its chunk_id in cited_chunk_ids.
- Do NOT promise a refund unless a refund has actually been looked up / processed in the scratchpad.
- If a high-impact action should follow (send_email, process_refund), list it in proposed_actions.
- Keep it to a few short paragraphs; no internal jargon."""


def draft_messages(state: SupportState):
    human = f"""Ticket: {state.ticket_subject}
{state.ticket_body}

Grounding & data gathered so far:
{_scratchpad_digest(state)}

Write the reply."""
    return [("system", DRAFT_SYSTEM), ("human", human)]


# ─────────────────────────────────────────────────────────────────────────────
# QA / policy guardrail
# ─────────────────────────────────────────────────────────────────────────────
QA_SYSTEM = """You are the QA/policy guardrail. Review a draft support reply before any human sees it,
and return a structured GuardrailResult.

Check for:
1. PII that should be redacted (emails, card numbers, phone numbers, addresses). If found, set
   pii_detected=true and provide redacted_body with the PII masked.
2. Policy violations — e.g. promising a refund when no process_refund appears in the scratchpad, or
   committing to anything we cannot keep. List each in policy_violations.
3. hallucination_risk=true when the draft asserts facts not supported by the retrieved chunks /
   looked-up data.

Set passed=false if there is any hard policy violation or hallucination risk (PII alone can pass if
you supply redacted_body). Put a short rationale in notes."""


def qa_messages(draft: DraftReply, state: SupportState):
    human = f"""Draft reply:
{draft.body}

Cited chunk ids: {draft.cited_chunk_ids}
Evidence available in scratchpad:
{_scratchpad_digest(state)}

Review the draft."""
    return [("system", QA_SYSTEM), ("human", human)]
