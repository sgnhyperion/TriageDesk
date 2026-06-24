"""Refund tool (MOCKED — no real payment provider). Owner: Member B. HIGH-IMPACT / HITL.

Refund is intentionally mocked per the project plan: instead of calling Stripe we
record the intent + outcome in the `refunds` table and write an audit_log entry.
This tool only runs AFTER a human approves (the brain pauses before it).

It figures out *what* to refund from the args the brain passes, falling back to
the most recent lookup_order result in the scratchpad (e.g. the duplicate charge).
"""
from __future__ import annotations

from contracts.schemas import SupportState, ToolName, ToolResult
from backend.db import queries


def _last_order_lookup(state: SupportState) -> dict | None:
    for result in reversed(state.scratchpad):
        if result.tool == ToolName.LOOKUP_ORDER and result.ok:
            return result.output
    return None


def process_refund(args: dict, state: SupportState) -> ToolResult:
    order_id = args.get("order_id")
    amount_cents = args.get("amount_cents")

    # Fall back to the duplicate charge surfaced by lookup_order.
    order_info = _last_order_lookup(state)
    if order_info:
        if not order_id and order_info.get("duplicate_order_ids"):
            order_id = order_info["duplicate_order_ids"][0]
        if amount_cents is None:
            amount_cents = order_info.get("duplicate_amount_cents")
    amount_cents = int(amount_cents or 0)

    # Record the (mock) refund. FK-safe subqueries -> NULL if ticket/order absent.
    refund = queries.execute(
        "insert into refunds (ticket_id, order_id, amount_cents, status) "
        "values ((select id from tickets where id = %s), "
        "        (select id from orders where id = %s), %s, 'processed') "
        "returning id, status, amount_cents",
        (state.ticket_id, order_id, amount_cents))

    # Reflect the refund on the order for a realistic demo.
    if order_id:
        queries.execute("update orders set status = 'refunded' where id = %s", (order_id,))

    detail = {"refund_id": refund["id"], "order_id": order_id,
              "amount_cents": amount_cents, "mock": True}
    queries.write_audit("process_refund", detail, ticket_id=state.ticket_id)
    state.audit_log.append(
        f"process_refund (mock): {refund['id']} for {amount_cents} cents")

    return ToolResult(tool=ToolName.PROCESS_REFUND, ok=True, output=queries.jsonable({
        "refund_id": refund["id"],
        "status": "processed_mock",
        "order_id": order_id,
        "amount_cents": amount_cents,
        "mock": True,
    }))
