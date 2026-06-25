# TriageDesk — 10-Minute Presentation Runbook

> Follows the official structure exactly. 10 min presentation + 5 min Q&A.
> **3 presenters.** Every section names who speaks. Practice to the clock.
>
> | # | Presenter | Slice |
> |---|---|---|
> | **P1** | Harsh Kumar (10116) | Member A — the Brain (LangGraph, supervisor, API) |
> | **P2** | Aman Yadav (10055) | Member B — Data, Tools, RAG, email |
> | **P3** | Harsh Kumar (10098) | Member C — Frontend, Eval, Demo |

---

## 0:00–1:00 — Problem, user, why it matters  ·  **P3 speaks**

> "Support teams face a constant tension between **speed and safety**. A single AI bot is fast but
> dangerous — it hallucinates answers, promises refunds it shouldn't, and leaks personal data. Pure
> human handling is safe but slow and expensive. **Our users are Tier-1 support agents and admins.**
> TriageDesk sits in the middle: an AI resolves tickets in seconds, but **a human approves every
> action that touches money or the customer.** Speed *and* safety."

- Show: the **inbox** with the 5 tickets (billing, bug, how-to, vague, out-of-scope) → "real support is wildly varied."

---

## 1:00–2:00 — Why it needs a multi-agent system  ·  **P1 speaks**

> "Two reasons. **One — different jobs, different agents:** understanding a ticket, finding the
> answer, writing the reply, and checking it for safety are *different skills with different failure
> modes*, so we split them into specialized agents. **Two — a dynamic brain, not a fixed script:**
> we have ~10 tools, and every ticket needs a different combination in a different order. You only
> discover the next step *after* the last one — look up an order, *oh it's a duplicate*, now propose a
> refund. A hard-coded flowchart would have to enumerate every path — intractable. So a **supervisor
> brain picks tools at runtime**, governed by guardrails."

---

## 2:00–4:00 — Architecture: agents, tools, state, routing, handoffs  ·  **P1 leads, P2 covers tools/data**

**P1 (2:00–3:10) — the brain & the graph:**
> "Four agents. A **Triage** agent classifies the ticket. The **Supervisor** is the brain — it reads
> the state, emits one structured **`Decision`** (which tool + why), runs it, and loops. A
> **Resolution** agent drafts the reply; a **QA** agent checks it for PII/policy/hallucination.
>
> Everything flows through one object — **`SupportState`** — and its **`scratchpad`**, the brain's
> working memory: the ordered list of tool results it reasons over before each decision.
>
> It's a real **LangGraph** graph: `START → supervisor → (continue → tools → loop)`, or
> `(await_human → interrupt → wait)`, or `(done/escalate/refuse → END)`. The pause is a true
> **`interrupt()`** persisted by a **Postgres checkpointer** keyed by ticket id — so approval can
> arrive in a *separate* HTTP request, even after a restart, and resume the exact run."

**P2 (3:10–4:00) — tools, data, RAG, handoffs:**
> "The brain acts on **10 tools**, all returning a structured **`ToolResult`** — CRM lookups,
> past-ticket search, bug filing, refund, draft, email. They're backed by **real Postgres**. For
> grounding we use **RAG over pgvector**: help docs are chunked, embedded to 768-dim vectors, and
> searched by meaning. Handoffs are all **Pydantic** — `Decision`, `ToolResult`, `Classification` —
> so the agents fit together by contract. Two things are mocked on purpose: inbound email (a 'new
> ticket' form) and the refund (writes a row, no Stripe) — the approval flow is identical either way."

---

## 4:00–7:00 — Working demo  ·  **P3 drives the UI; ticket owner narrates**

> Pre-warm before stage: run TCK-1003 once so the first LLM call isn't cold.
> One person (P3) clicks; the owner of each ticket talks over it.

**(4:00–5:15) TCK-1001 "Charged twice" — HITL hero · P1 narrates**
- Open → **▶ Run agent**. Trace: `lookup_customer → lookup_order` **(duplicate found)** `→ process_refund`.
- **Pauses.** "It discovered the refund only *after* the lookup. And it won't move money without a human." → **Approve refund** → continues to draft + send.

**(5:15–6:00) TCK-1002 "App crashes on PDF export" — RAG, no refund · P2 narrates**
- Run → `search_past_tickets` + `retrieve_kb` find the known v3.2 fix → grounded reply, **no refund**.
- "Backed by real Postgres + a pgvector knowledge base. A bug isn't a refund — different tools."

**(6:00–6:30) TCK-1005 "Write my essay" — guardrail · P3 narrates**
- Run → brain **refuses politely**, zero tools run. "Out-of-scope is refused, not answered."

**(6:30–7:00) Admin · P3 narrates**
- Switch to admin → **Analytics** cards → **upload a KB doc** → re-run a related ticket, now cites it.
- "Agents are blocked from /admin — role-gated."

---

## 7:00–8:30 — Evaluation, guardrails, debugging, limitations  ·  **P3 speaks (P1 on guardrails)**

**P3 — evaluation & debugging:**
> "We have **11 evaluation scenarios** — `pytest backend/tests/test_eval.py`, all green. Each asserts
> on the brain's **tool path** and **final outcome** for a ticket type. They're **deterministic**: the
> decider is injectable, so we test the loop, guardrails, and routing — not the LLM's random sampling —
> and they run with no API key in under a second. **92 tests pass overall.** For debugging we use
> **LangSmith**: every LLM call and graph step is traced, which is how we caught issues like the brain
> looping or picking a wrong tool."

**P1 — guardrails (the governance):**
> "Eight guardrails keep the brain safe: **out-of-scope → refuse**; **low confidence → escalate**;
> **critical severity → escalate**; **step budget of 8 → escalate** (no infinite loops); **grounding
> floor** (KB match below threshold → escalate, no hallucination); **QA/PII pass** on every draft;
> an **allow-list** (the brain may only emit a valid tool name); and **mandatory human approval**
> before refund and email."

**Limitations (be honest — evaluators reward it):**
> "Refund and inbound email are mocked; the resume path has one reconciliation TODO; RAG is
> single-vector (no re-ranker yet); and the trace is shown after the run, not streamed live."

---

## 8:30–10:00 — Individual contributions  ·  **each speaks ~30s**

**P1 — Harsh Kumar (10116), Member A:**
> "I built the brain: the supervisor loop and guardrails, the 3 LLM agents, the LangGraph graph with
> the Postgres-checkpointer HITL, the provider-swappable LLM factory (Gemini *or* Claude), auth, and
> the FastAPI surface."

**P2 — Aman Yadav (10055), Member B:**
> "I built everything the brain acts on: the Postgres schema + seed data, the 10 tools, the RAG
> pipeline (embeddings → pgvector → retrieve with a grounding threshold), live KB upload, Resend
> email, the refund mock, the audit log, and the analytics queries."

**P3 — Harsh Kumar (10098), Member C:**
> "I built the product: the Next.js UI, the reasoning-trace view, the human-approval panel, the admin
> screens, demo mode, and the 11-scenario evaluation suite and demo."

---

## Q&A (10:00–15:00) — likely questions, who answers

| Question | Lead |
|---|---|
| Why a dynamic brain, not a fixed pipeline? | P1 |
| How does the pause survive two HTTP requests? | P1 |
| How do you stop hallucination? | P2 |
| Why pgvector over a dedicated vector DB? | P2 |
| How do you test a non-deterministic LLM? | P3 |
| What's mocked and why? | P2 |
| What stops infinite loops / bad tools? | P1 |

---

## Pre-flight checklist (before the slot)
- [ ] `./run.sh` (backend up) + `cd frontend && npm run dev` (frontend up).
- [ ] Inbox shows TCK-1001..1005. Pre-warm: run TCK-1003 once.
- [ ] Logged in as **agent**; know the **admin** login for the admin step.
- [ ] Fallback ready: if the live LLM hiccups, demo mode (amber banner, fixtures) clicks through the same flow.
- [ ] Screenshots/GIF of each step saved as a last resort.
- [ ] One laptop drives; rehearsed once end-to-end to the clock.
