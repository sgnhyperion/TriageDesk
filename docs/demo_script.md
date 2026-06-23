# Demo Script — TriageDesk

> Owner: **Member C**. This is a starter skeleton (placeholder so the path the
> other docs reference resolves). Fill in exact clicks/inputs once the UI is live.
> Maps to the brief's 4–7 min "working demo" slot.

## Setup (before presenting)
- Backend running (`uvicorn backend.main:app`), frontend running (`npm run dev`), DB seeded.
- Pre-warm the deployed URLs so there's no cold start.
- Have the 5 sample tickets from `contracts/fixtures/sample_tickets.json` loaded.

## Flow (target ~3 min)
1. **Log in** as a support agent → show the inbox.
2. **Happy path (how-to):** open "How do I change my plan?" → Run agent →
   show the **reasoning trace** (retrieve_kb → draft_reply) → approve → reply "sent".
3. **High-impact (billing/refund):** open "Charged twice this month" → Run agent →
   trace shows lookup_customer → lookup_order (duplicate found) → process_refund →
   **system pauses for approval** → approve → refund + email.  ← the HITL moment.
4. **Guardrail (out-of-scope):** open "Write my essay" → agent **refuses** politely.
5. **Admin:** upload a new KB doc → re-run a related ticket → agent now cites it.

## Talking points to hit
- Why a dynamic brain (different tools per ticket, decided at runtime).
- Structured handoffs (Decision / ToolResult) + conditional routing.
- Guardrails + human-in-the-loop on every high-impact action.
- LangSmith trace for one ticket (observability).

## TODO(Member C)
- [ ] Exact ticket IDs + expected trace for each demo step.
- [ ] Screenshot/GIF fallback in case live demo fails.
