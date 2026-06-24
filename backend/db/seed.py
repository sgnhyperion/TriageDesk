"""
Seed realistic demo data. Owner: Member B.

This populates the "world" the brain acts on so the §7 eval scenarios work
end-to-end:

  • customers / orders / subscriptions backing lookup_customer/order/subscription
  • a DUPLICATE CHARGE on CUST-42 (two identical orders same day) — the headline
    billing case: lookup_order detects it -> propose refund
  • an enterprise order > $100 (CUST-23) — the refund>$100 escalation policy case
  • ~5 RESOLVED past tickets so search_past_tickets finds prior issues
    (incl. the PDF-export crash that makes TCK-1002 a "known bug")

The OPEN demo tickets (TCK-1001..1005) are loaded from
contracts/fixtures/sample_tickets.json so the DB stays in sync with the exact
tickets Member C's UI and the eval use — the fixtures remain the single source
of truth; this file only adds the supporting world.

Idempotent: every insert is ON CONFLICT DO NOTHING, so re-running is safe.

Usage (after apply_schema.py):
    python backend/db/seed.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Allow running directly (`python backend/db/seed.py`) as well as `-m`.
if __package__ in (None, "") and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.db import queries

_FIXTURES = _REPO_ROOT / "contracts" / "fixtures" / "sample_tickets.json"


# ─── customers ───────────────────────────────────────────────────────────────
CUSTOMERS = [
    # id,        name,            email,                 plan
    ("CUST-42", "Alice Nguyen",  "alice@example.com",   "pro"),
    ("CUST-7",  "Bob Martin",    "bob@example.com",     "pro"),
    ("CUST-15", "Carol Singh",   "carol@example.com",   "free"),
    ("CUST-99", "Dave Lee",      "dave@example.com",    "free"),
    ("CUST-23", "Erin Costa",    "erin@example.com",    "enterprise"),
]

# ─── orders (amount in cents) ────────────────────────────────────────────────
ORDERS = [
    # id,        customer,   cents, currency, status,  charged_at,                 description
    # CUST-42: DUPLICATE CHARGE — two identical Pro charges on the same day.
    ("ORD-9001", "CUST-42",  2900, "usd", "paid", "2026-06-03T10:01:00Z", "Pro plan monthly"),
    ("ORD-9002", "CUST-42",  2900, "usd", "paid", "2026-06-03T10:04:00Z", "Pro plan monthly"),
    ("ORD-9003", "CUST-7",   2900, "usd", "paid", "2026-06-01T12:00:00Z", "Pro plan monthly"),
    # CUST-23: enterprise charge over $100 -> refund needs escalation per policy.
    ("ORD-9004", "CUST-23", 12000, "usd", "paid", "2026-06-10T09:00:00Z", "Enterprise plan monthly"),
]

# ─── subscriptions ───────────────────────────────────────────────────────────
SUBSCRIPTIONS = [
    # id,        customer,   plan,          status,   renews_at
    ("SUB-7001", "CUST-42", "pro",        "active",   "2026-07-03T00:00:00Z"),
    ("SUB-7002", "CUST-7",  "pro",        "active",   "2026-07-01T00:00:00Z"),
    ("SUB-7003", "CUST-23", "enterprise", "active",   "2026-07-10T00:00:00Z"),
    ("SUB-7004", "CUST-15", "free",       "active",   None),
]

# ─── resolved PAST tickets (history for search_past_tickets) ─────────────────
PAST_TICKETS = [
    # id,        customer,   subject,                                   body,                                                              category,  severity, sentiment, final_reply
    ("TCK-0901", "CUST-7",  "PDF export crashes the app",              "Export to PDF crashes on v3.2.",                                  "bug",     "medium", "neutral", "Known issue on v3.2 — upgrade to v3.3+ which fixes PDF export."),
    ("TCK-0902", "CUST-42", "Double charged for my subscription",      "I was billed twice this month.",                                  "billing", "high",   "negative", "Confirmed duplicate charge; full refund issued."),
    ("TCK-0903", "CUST-15", "How do I reset my password?",             "I forgot my password and can't log in.",                          "how_to",  "low",    "neutral", "Use Forgot password on the login screen; a reset link is emailed."),
    ("TCK-0904", "CUST-7",  "Upgrade from Free to Pro",                "How do I change my plan to Pro?",                                 "how_to",  "low",    "neutral", "Settings > Billing > Plan; upgrades take effect immediately."),
    ("TCK-0905", "CUST-23", "Cancel my enterprise subscription",       "I want to cancel and get a refund.",                              "refund",  "high",   "negative", "Cancellation processed; refund over $100 escalated to billing team."),
]


def _seed_customers() -> int:
    n = 0
    for cid, name, email, plan in CUSTOMERS:
        queries.execute(
            "insert into customers (id, name, email, plan) values (%s,%s,%s,%s) "
            "on conflict (id) do nothing",
            (cid, name, email, plan),
        )
        n += 1
    return n


def _seed_orders() -> int:
    for oid, cust, cents, cur, status, charged_at, desc in ORDERS:
        # Upsert amount/status so re-seeding RESTORES the demo state — e.g. the
        # CUST-42 duplicate charge that a prior refund (demo or test) consumed.
        queries.execute(
            "insert into orders (id, customer_id, amount_cents, currency, status, charged_at, description) "
            "values (%s,%s,%s,%s,%s,%s,%s) "
            "on conflict (id) do update set amount_cents = excluded.amount_cents, status = excluded.status",
            (oid, cust, cents, cur, status, charged_at, desc),
        )
    return len(ORDERS)


def _seed_subscriptions() -> int:
    for sid, cust, plan, status, renews_at in SUBSCRIPTIONS:
        queries.execute(
            "insert into subscriptions (id, customer_id, plan, status, renews_at) "
            "values (%s,%s,%s,%s,%s) on conflict (id) do nothing",
            (sid, cust, plan, status, renews_at),
        )
    return len(SUBSCRIPTIONS)


def _seed_past_tickets() -> int:
    for tid, cust, subject, body, cat, sev, sent, reply in PAST_TICKETS:
        queries.execute(
            "insert into tickets (id, customer_id, subject, body, category, severity, sentiment, status, final_reply) "
            "values (%s,%s,%s,%s,%s,%s,%s,'resolved',%s) on conflict (id) do nothing",
            (tid, cust, subject, body, cat, sev, sent, reply),
        )
    return len(PAST_TICKETS)


def _seed_open_tickets() -> int:
    """The live demo tickets — loaded from the fixtures so the DB matches exactly
    what the UI and eval use."""
    tickets = json.loads(_FIXTURES.read_text())
    for t in tickets:
        queries.execute(
            "insert into tickets (id, customer_id, subject, body, category, severity, sentiment, status) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict (id) do nothing",
            (t["id"], t.get("customer_id"), t["subject"], t["body"],
             t.get("category"), t.get("severity"), t.get("sentiment"),
             t.get("status", "open")),
        )
    return len(tickets)


def seed_all() -> dict:
    counts = {
        "customers": _seed_customers(),
        "orders": _seed_orders(),
        "subscriptions": _seed_subscriptions(),
        "past_tickets": _seed_past_tickets(),
        "open_tickets": _seed_open_tickets(),
    }
    return counts


if __name__ == "__main__":
    result = seed_all()
    for table, n in result.items():
        print(f"  seeded {n:>2} {table}")
    print("Seed complete.")
