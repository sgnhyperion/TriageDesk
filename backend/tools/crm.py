"""CRM lookup tools — backed by the Supabase/Postgres CRM tables. Owner: Member B.

Each tool is a standalone function `fn(args, state) -> ToolResult` (the A↔B
contract in tools/registry.py). They read the customers/orders/subscriptions
tables and return JSON-safe `output` the brain can reason over.

Design note: "not found" is a normal result, not a failure — we return ok=True
with `found=False` so the brain can decide what to do, and reserve ok=False for
genuine errors (handled centrally in registry.dispatch).
"""
from __future__ import annotations

from contracts.schemas import SupportState, ToolName, ToolResult
from backend.db import queries


def _customer_id(args: dict, state: SupportState) -> str | None:
    return args.get("customer_id") or state.customer_id


def lookup_customer(args: dict, state: SupportState) -> ToolResult:
    """Fetch a customer (and a quick account summary) by id."""
    cid = _customer_id(args, state)
    if not cid:
        return ToolResult(tool=ToolName.LOOKUP_CUSTOMER, ok=True,
                          output={"found": False, "reason": "no customer_id on ticket or args"})

    customer = queries.fetch_one(
        "select id, name, email, plan, created_at from customers where id = %s", (cid,))
    if not customer:
        return ToolResult(tool=ToolName.LOOKUP_CUSTOMER, ok=True,
                          output={"found": False, "customer_id": cid})

    counts = queries.fetch_one(
        "select "
        "  (select count(*) from orders where customer_id = %s) as order_count, "
        "  (select count(*) from subscriptions where customer_id = %s) as subscription_count",
        (cid, cid))

    return ToolResult(tool=ToolName.LOOKUP_CUSTOMER, ok=True, output=queries.jsonable({
        "found": True,
        "customer": customer,
        "order_count": counts["order_count"],
        "subscription_count": counts["subscription_count"],
    }))


def lookup_order(args: dict, state: SupportState) -> ToolResult:
    """List a customer's orders and DETECT DUPLICATE CHARGES.

    A duplicate = ≥2 paid orders with the same amount (the headline billing case:
    the brain sees `duplicate_charge=True` → proposes a refund). Also reports the
    total refundable amount so the brain/escalation policy can reason about it.
    """
    cid = _customer_id(args, state)
    if not cid:
        return ToolResult(tool=ToolName.LOOKUP_ORDER, ok=True,
                          output={"found": False, "reason": "no customer_id on ticket or args"})

    orders = queries.fetch_all(
        "select id, customer_id, amount_cents, currency, status, charged_at, description "
        "from orders where customer_id = %s order by charged_at",
        (cid,))

    # Group paid orders by amount to find duplicate charges.
    by_amount: dict[int, list[dict]] = {}
    for o in orders:
        if o["status"] == "paid":
            by_amount.setdefault(o["amount_cents"], []).append(o)

    duplicate_groups = [grp for grp in by_amount.values() if len(grp) > 1]
    duplicate_charge = bool(duplicate_groups)
    duplicate_order_ids = [o["id"] for grp in duplicate_groups for o in grp]
    # Refundable = one charge per duplicate group (the extra charge(s)).
    duplicate_amount_cents = sum(grp[0]["amount_cents"] * (len(grp) - 1) for grp in duplicate_groups)

    return ToolResult(tool=ToolName.LOOKUP_ORDER, ok=True, output=queries.jsonable({
        "found": bool(orders),
        "customer_id": cid,
        "orders": orders,
        "order_count": len(orders),
        "duplicate_charge": duplicate_charge,
        "duplicate_order_ids": duplicate_order_ids,
        "duplicate_amount_cents": duplicate_amount_cents,
    }))


def check_subscription_status(args: dict, state: SupportState) -> ToolResult:
    """Report a customer's subscription(s): plan, status, renewal date."""
    cid = _customer_id(args, state)
    if not cid:
        return ToolResult(tool=ToolName.CHECK_SUBSCRIPTION_STATUS, ok=True,
                          output={"found": False, "reason": "no customer_id on ticket or args"})

    subs = queries.fetch_all(
        "select id, customer_id, plan, status, renews_at, created_at "
        "from subscriptions where customer_id = %s order by created_at desc",
        (cid,))

    return ToolResult(tool=ToolName.CHECK_SUBSCRIPTION_STATUS, ok=True, output=queries.jsonable({
        "found": bool(subs),
        "customer_id": cid,
        "subscriptions": subs,
        "active": any(s["status"] == "active" for s in subs),
    }))
