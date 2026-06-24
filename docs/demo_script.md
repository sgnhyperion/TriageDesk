# Demo Script — TriageDesk

> Owner: **Member C**. Maps to the brief's 4–7 min "working demo" slot.
> The frontend runs standalone (mock auth + fixture fallback) so the demo works
> even if the live backend hiccups — see the fallback note at the bottom.

## Setup (before presenting)
- **Live path:** backend running (`uvicorn backend.main:app --reload`), frontend
  running (`cd frontend && npm run dev`), DB seeded. Pre-warm deployed URLs to
  avoid cold starts.
- **Safe path:** if no Supabase keys / backend, the UI auto-runs in **demo mode**
  (amber banner): one-click role sign-in + the 5 sample tickets load from
  `contracts/fixtures/sample_tickets.json`.
- Sign in once as **agent** (ticket flows) and know the **admin** login for step 5.

## Ticket IDs used (from `contracts/fixtures/sample_tickets.json`)
| ID | Subject | Demo role |
|----|---------|-----------|
| TCK-1003 | "How do I change my plan?" | Happy path (how-to) |
| TCK-1001 | "Charged twice this month" | High-impact HITL (refund/send) |
| TCK-1005 | "Write my college essay" | Guardrail (out-of-scope refuse) |

## Flow (target ~3 min)

1. **Log in** as a support agent → land on the **Inbox**. Point out status
   filters and the **+ New ticket** button (the mocked inbound email).

2. **Happy path — TCK-1003 ("How do I change my plan?")**
   - Open it → click **▶ Run agent**.
   - **Reasoning trace** appears as a timeline. Expected steps (stub brain):
     `retrieve_kb → draft_reply → send_email`.
   - The brain pauses on `send_email` → the **draft reply** + **QA check** card
     show, and the amber **Action required** panel appears.
   - Click **Approve** → "Sent reply" banner; ticket resolves.
   - *(Also show **Edit & approve** — edit the draft inline before sending.)*

3. **High-impact — TCK-1001 ("Charged twice this month")** ← the HITL moment
   - Open it → **▶ Run agent**.
   - Trace (per `sample_trace.json`): `lookup_customer → lookup_order
     (duplicate found) → retrieve_kb (policy) → process_refund`.
   - System **pauses for approval** on `process_refund` → panel shows
     **Approve refund / Escalate / Reject**.
   - Click **Approve refund** → the brain continues to draft + send. Emphasize:
     *no money moves and no email goes out without a human click.*

4. **Guardrail — TCK-1005 ("Write my college essay")**
   - Open it → **▶ Run agent** → the brain **refuses** politely
     (out-of-scope banner). No tools run, no reply sent.

5. **Admin — switch to the admin account**
   - Open **Admin** → **Analytics** cards (totals, escalation rate, avg steps).
   - **Upload a KB doc** → re-run a related ticket → the agent now cites it.
   - Show that an **agent** account is blocked from `/admin` (role-gating).

## Talking points to hit
- **Why a dynamic brain:** different tools per ticket, chosen at runtime from the
  last result (TCK-1001 discovered the refund only after the order lookup).
- **Structured handoffs:** `Decision` / `ToolResult` + conditional routing
  (continue / await_human / escalate / refuse / done).
- **Guardrails + HITL:** step budget, allow-list, out-of-scope refusal, QA/PII
  check, and a mandatory human approval on every high-impact action.
- **Observability:** the reasoning-trace view is the scratchpad made visible;
  LangSmith trace for one ticket (once wired by Member A).

## Fallback if the live demo fails
- The UI stays fully clickable in **demo mode** — narrate the same flow against
  fixtures; the trace, draft, QA flags, and approval panel all render from
  `sample_*.json`.
- Keep a **screenshot/GIF** of each step (inbox → trace → approval → resolved)
  as a last resort.

## TODO(Member C) — when the real brain lands (Member A)
- [ ] Replace stub-trace expectations in step 2/3 with the real Gemini tool paths.
- [ ] Re-record screenshots/GIF against the live brain.
- [ ] Enable the 6 skipped eval scenarios in `backend/tests/test_eval.py`.
