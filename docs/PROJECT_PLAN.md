# TriageDesk — Project Plan & Team Playbook

**Course:** Multi-Agent Orchestration [AI/ML] — Capstone
**Project:** A real, multi-agent AI Support Desk built on a governed *supervisor brain* (LangGraph)
**Team:** 3 developers
**Stack:** FastAPI + LangGraph (Python) · Next.js (frontend) · Supabase (Postgres + Auth + pgvector + Storage) · Gemini (LLM + embeddings) · Resend (real outbound email) · LangSmith (tracing)

> This document is the single source of truth. It consolidates everything: the problem,
> why it needs multi-agent, the architecture, the data model, the code structure, the
> three frozen interface contracts, and the detailed per-member ownership and tasks.

---

## 1. Problem Statement

Support teams face a constant tension between **speed** and **safety**:

- **Full automation** (a single LLM bot) hallucinates answers, promises refunds it shouldn't,
  leaks PII, and mishandles angry customers — high risk on customer-facing actions.
- **Pure manual handling** is slow and expensive, and agents repeatedly re-solve the same issues.

Real support requests are also **wildly varied**: a billing dispute, a how-to question, a bug
report, a vague "it's not working", and a refund demand each require *different information,
different tools, and a different sequence of steps* — and which steps are needed often only
becomes clear *after* looking something up.

**TriageDesk** is an AI support desk where a team logs in, tickets arrive, and a **governed
supervisor agent (the "brain")** dynamically decides — per ticket, step by step — which tools to
use to resolve it: look up the customer/order, search the knowledge base, search past tickets,
file a bug, propose a refund, ask for more info, draft a reply. **Every high-impact action
(sending the email, processing a refund) pauses for a human to approve.**

- **Target users:** Tier-1 support **agents** (resolve tickets) and **admins** (manage the
  knowledge base, view analytics).
- **Core value proposition:** *Grounded, policy-checked resolutions in seconds — with a human in
  control of every customer-facing action.*

---

## 2. Why this requires a multi-agent system (and a dynamic brain)

This is the make-or-break narrative for the evaluation (rubric: *Problem clarity 10% +
Multi-agent architecture 20%*). Two-part argument:

**(a) Why multiple specialized agents, not one prompt:** understanding a ticket (classification),
finding truth (retrieval), composing a safe reply (drafting), and judging it (QA/policy) are
*different jobs with different failure modes*. Separating them lets us independently route, ground,
guardrail, and verify — impossible to do cleanly inside a single prompt.

**(b) Why a *dynamic supervisor brain*, not a fixed pipeline:** with **~9 heterogeneous tools** and
**unpredictable request types**, the set, order, and number of steps cannot be known in advance.
A static graph would have to hard-code every path combination — combinatorially intractable and
brittle. The brain instead **selects tools at runtime based on intermediate results, and
re-plans** (e.g. *order lookup reveals a duplicate charge → propose refund*; *KB miss → search
past tickets → file a bug*). No two tickets take the same path.

**Concrete unpredictable paths (these double as eval cases):**

| Ticket | Tool path the brain discovers |
|---|---|
| "Charged twice this month" | `lookup_customer` → `lookup_order` → (dup charge) → `process_refund`★ → `draft_reply` → `send_email`★ |
| "App crashes on export" | `search_past_tickets` → (no match) → `create_bug_report` → `retrieve_kb` (workaround) → `draft_reply` → `send_email`★ |
| "It's not working" (vague) | `request_more_info` → **pause/loop** → (reply) → re-plan |
| "How do I change my plan?" | `retrieve_kb` → `draft_reply` → `send_email`★ |
| "Cancel and refund my subscription" | `check_subscription_status` → `lookup_order` → `process_refund`★ → `escalate` (policy) |

★ = high-impact → **human approval required** before it executes.

---

## 3. Architecture

### 3.1 The governed supervisor brain

```
                                    ┌──────────────────────────┐
   new ticket ───────────────────►  │   SUPERVISOR (brain)     │ ◄──────────┐
                                    │  reads SupportState →    │            │ loop until
                                    │  Decision{next_tool,     │            │ finish / escalate
                                    │  args, reason} (struct)  │            │ / step-budget hit
                                    └─────────────┬────────────┘            │
                                                  │ selects ONE tool/step   │
   ┌───────────┬───────────┬───────────┬─────────┼─────────┬───────────┬───┴────┬──────────┐
   ▼           ▼           ▼           ▼          ▼         ▼           ▼        ▼          ▼
lookup_   lookup_   check_sub_   retrieve_  search_past  create_   request_  process_  send_email
customer  order     status       kb (RAG)   _tickets     bug_report more_info refund★   + finish
                                                                              (MOCK,HITL)(Resend,HITL)
```

**Loop:** Supervisor reads `SupportState` (especially `scratchpad`, its working memory) → emits a
structured `Decision` → the chosen tool runs → its `ToolResult` is appended to `scratchpad` → back
to the Supervisor → repeat until `finish` / `escalate` / step-budget. High-impact tools trigger a
LangGraph `interrupt()` for human approval before they execute.

### 3.2 The tool registry (9 tools + 2 control actions)

| Tool | Backed by | High-impact (HITL)? |
|---|---|---|
| `lookup_customer` | Postgres `customers` | no |
| `lookup_order` | Postgres `orders` | no |
| `check_subscription_status` | Postgres `subscriptions` | no |
| `retrieve_kb` | pgvector (RAG) | no |
| `search_past_tickets` | Postgres `tickets` | no |
| `create_bug_report` | Postgres `bug_reports` | no |
| `request_more_info` | sets state → pause/loop | no |
| `process_refund` | **MOCK** (`refunds` row) | **✅** |
| `draft_reply` | LLM | no |
| `send_email` | **Resend (real)** | **✅** |
| `escalate`, `finish` | control | — |

### 3.3 Guardrails (what makes the brain *governed*)

- **Step budget** (`max_steps`, default 8) → force escalate if exceeded (prevents infinite loops).
- **Allow-list:** the brain may only emit a `ToolName` from the enum; invalid → reject + re-prompt.
- **Confidence floor / severity rule:** low confidence or refund/legal/critical → must escalate.
- **Out-of-scope refusal:** `in_scope == false` → polite refusal, no tools run.
- **QA/policy pass** on every draft: PII detection + redaction, policy checks (e.g. no refund
  promised without the refund tool + approval), hallucination check vs. retrieved chunks.
- **Mandatory HITL** before `process_refund` and `send_email`.

### 3.4 Human-in-the-loop

LangGraph **Postgres checkpointer + `interrupt()`**. When the brain selects a high-impact tool, the
graph pauses and persists. The frontend shows the draft + sources + QA flags; the human picks
**Approve / Edit & Approve / Escalate / Approve refund / Reject**; `POST /tickets/{id}/decision`
resumes the graph, which then runs the Executor to perform the real action.

### 3.5 Tech stack & reasoning

| Layer | Choice | Why |
|---|---|---|
| Orchestration | **LangGraph (Python)** | Rubric names it (15%); most mature for supervisor + HITL |
| Backend | **FastAPI** | Hosts the graph; clean OpenAPI contract for the frontend |
| LLM + embeddings | **Gemini** (`gemini-*` + `text-embedding-004`) behind `get_llm()` | Free tier; one-provider key; swappable in one line |
| Frontend | **Next.js (App Router) + Tailwind** | Real auth flows + SaaS UI; deploys to Vercel |
| Auth | **Supabase Auth** (roles: agent/admin) | Same service as DB; RLS |
| DB + vectors + files | **Supabase** (Postgres + pgvector + Storage) | One service for data, RAG, uploads |
| Email | **Resend** | Real outbound, free tier, simplest |
| Observability | **LangSmith** + in-app analytics dashboard | Traces + metrics |
| Deploy | **Vercel** (frontend) · **Render/Railway** (FastAPI) · **Supabase** (DB) | Free tiers; clean separation |

### 3.6 Real vs. mocked (intentional, approved)

- **Real:** auth, Postgres ticket store, RAG/pgvector, the 5-agent brain + routing + structured
  outputs, **outbound email (Resend)**, **live admin KB document upload**, LangSmith, analytics.
- **Mocked (plumbing cost only):** **inbound email** (a "new ticket" form / "simulate incoming
  email" button creates the ticket); **refund** (writes a `refunds` row instead of calling Stripe).

---

## 4. The 3 Frozen Contracts (freeze in Hour 1, before feature code)

A *contract* is an agreed interface between two people's code, written down and locked, so all 3
can build in parallel against stubs without waiting. Changing one requires announcing it first.

| Contract | File | Pins down | Between |
|---|---|---|---|
| 1. API surface | [`contracts/openapi.yaml`](../contracts/openapi.yaml) | REST endpoints + JSON shapes | Backend (A) ↔ Frontend (C) |
| 2. Agent schemas | [`contracts/schemas.py`](../contracts/schemas.py) | Pydantic handoff models + `SupportState` | Agents (A) ↔ Tools (B) |
| 3. Database schema | [`contracts/schema.sql`](../contracts/schema.sql) | Tables, vector fn, RLS | Data (B) ↔ everyone |

These three files are **already written** in `contracts/`. Step 1 of the project is for all three of
you to read them together, agree, and commit them to `main`. Everything else branches from there.

---

## 5. Code / Folder Structure

```
.                                   # <-- your repo root (this folder)
├── contracts/                      # FROZEN — read & agree Hour 1 (ALL)
│   ├── schemas.py                  #   Pydantic agent-handoff models
│   ├── schema.sql                  #   Supabase tables + pgvector + RLS
│   ├── openapi.yaml                #   REST surface (frontend ↔ backend)
│   └── fixtures/                   #   shared sample JSON for parallel dev
│
├── backend/                        # Python — FastAPI + LangGraph
│   ├── main.py                     #   FastAPI app entry                    (A)
│   ├── api/                        #   route handlers (tickets, kb, analytics)(A)
│   ├── graph.py                    #   supervisor graph build + edges        (A)
│   ├── supervisor.py               #   the brain: Decision loop + guardrails (A)
│   ├── state.py                    #   imports SupportState from contracts   (A)
│   ├── llm.py                      #   get_llm() Gemini factory + retry      (A)
│   ├── checkpointer.py             #   Postgres checkpointer (HITL)          (A)
│   ├── agents/
│   │   ├── triage.py               #   classification agent                  (A)
│   │   ├── resolution.py           #   draft_reply agent                     (A)
│   │   └── qa_review.py            #   guardrail/policy agent                (A)
│   ├── tools/                      #   the 9-tool registry                   (B)
│   │   ├── registry.py             #   ToolName -> callable mapping          (A+B contract)
│   │   ├── crm.py                  #   lookup_customer/order/subscription    (B)
│   │   ├── tickets.py              #   search_past_tickets, create_bug_report(B)
│   │   ├── refund.py               #   process_refund (mock)                 (B)
│   │   └── info.py                 #   request_more_info                     (B)
│   ├── rag/
│   │   ├── ingest.py               #   chunk + embed + index (KB upload)     (B)
│   │   ├── embed.py                #   Gemini embeddings                     (B)
│   │   └── retrieve.py             #   retrieve_kb (pgvector)                (B)
│   ├── integrations/
│   │   └── email_resend.py         #   send_email (real)                     (B)
│   ├── db/                         #   Supabase client + queries             (B)
│   ├── analytics.py                #   dashboard aggregation                 (B)
│   ├── requirements.txt            #   backend deps                          (A)
│   └── tests/                      #   eval suite (5+ cases)                 (C)
│
├── frontend/                       # Next.js (App Router) + Tailwind          (C)
│   ├── app/
│   │   ├── login/                  #   Supabase Auth
│   │   ├── inbox/                  #   ticket list
│   │   ├── tickets/[id]/           #   detail + brain trace + approval UI
│   │   └── admin/                  #   KB upload + analytics dashboard
│   ├── lib/api.ts                  #   typed client for openapi.yaml
│   └── lib/supabase.ts             #   auth/session
│
├── docs/
│   ├── PROJECT_PLAN.md             #   this file
│   ├── architecture.png            #   diagram for the slides
│   └── demo_script.md              #   the live-demo walkthrough           (C)
│
├── data/kb/                        # seed help docs (initial KB)            (B)
└── README.md                       #   setup + run + architecture summary  (A)
```
> Deps & secrets live next to their stack: backend → `backend/requirements.txt` + `backend/.env.example`;
> frontend → `frontend/package.json` + `frontend/.env.local.example`.

---

## 6. Team Division — Detailed Ownership

Three **vertical slices** that meet only at the three frozen contracts. After Hour 1, no member
blocks another.

### Member A — Backend & Agents Lead (the brain)

**Mission:** own the supervisor brain, the LangGraph wiring, HITL, and the FastAPI surface.

**Responsibilities**
- The Supervisor loop: read state → produce structured `Decision` → dispatch tool → repeat.
- Brain guardrails: step budget, tool allow-list, confidence/severity escalation, validation-retry
  on Gemini structured output.
- The 3 LLM agents (`triage`, `resolution`/draft_reply, `qa_review`).
- LangGraph graph + conditional edges + Postgres checkpointer (HITL `interrupt`/resume).
- `get_llm()` Gemini factory (+ retry/backoff for rate limits).
- FastAPI routes implementing `openapi.yaml`; JWT validation; LangSmith wiring.

**Files owned:** `backend/main.py`, `backend/api/`, `backend/graph.py`, `backend/supervisor.py`,
`backend/state.py`, `backend/llm.py`, `backend/checkpointer.py`, `backend/agents/*`,
`backend/tools/registry.py` (the dispatch contract), `backend/requirements.txt`, `README.md`.

**Task checklist**
- [ ] Read & co-sign the 3 contracts; commit to `main`.
- [ ] `get_llm()` returns a working Gemini client; smoke-test a structured output.
- [ ] Supervisor loop on **2 stub tools** end-to-end (prove the loop + scratchpad first).
- [ ] Triage agent → `Classification`.
- [ ] QA/guardrail agent → `GuardrailResult`; resolution agent → `DraftReply`.
- [ ] Conditional edges: continue / await_human / escalate / refuse / done.
- [ ] Postgres checkpointer + `interrupt()` before high-impact tools; resume on decision.
- [ ] Wire real tools (from B) into the registry, replacing stubs.
- [ ] FastAPI endpoints: `/tickets`, `/tickets/{id}`, `/run`, `/trace`, `/decision`, `/kb/upload`, `/analytics`, `/health`.
- [ ] LangSmith tracing on.

**Expected commits (representative):** `feat: gemini get_llm factory` · `feat: supervisor loop on stubs`
· `feat: triage + qa agents` · `feat: conditional routing edges` · `feat: postgres checkpointer + HITL interrupt`
· `feat: tool registry dispatch` · `feat: fastapi ticket+decision routes` · `chore: langsmith tracing`.

**Deliverables:** a running governed brain behind the REST API, with working HITL pause/resume.

---

### Member B — Data, RAG & Integrations Lead (the tools & the world)

**Mission:** own everything the brain *acts on* — the database, the 9 tools' data backings, RAG,
real email, the mocked refund, audit log, and analytics queries.

**Responsibilities**
- Supabase project: run `schema.sql`, seed `customers`/`orders`/`subscriptions`/sample tickets.
- The data-backed tools: `lookup_customer`, `lookup_order`, `check_subscription_status`,
  `search_past_tickets`, `create_bug_report`, `request_more_info`, `process_refund` (mock).
- RAG pipeline: Gemini embeddings, pgvector `retrieve_kb`, and **live KB upload** (chunk → embed →
  index) backing `POST /kb/upload`.
- Real outbound email via Resend (`send_email`).
- Audit log writes on every high-impact action; analytics aggregation queries.

**Files owned:** `contracts/schema.sql`, `backend/db/`, `backend/tools/{crm,tickets,refund,info}.py`,
`backend/rag/{ingest,embed,retrieve}.py`, `backend/integrations/email_resend.py`,
`backend/analytics.py`, `data/kb/`.

**Task checklist**
- [ ] Read & co-sign the 3 contracts; finalize `schema.sql`; run on a fresh Supabase project.
- [ ] Seed realistic sample data (customers, orders incl. a duplicate charge, subscriptions, ~5 past tickets).
- [ ] Implement each tool as a standalone, unit-testable function returning a `ToolResult`.
- [ ] Gemini embeddings + ingest a seed KB from `data/kb/`; `retrieve_kb` returns `RetrievedContext`
      with `has_grounding` thresholding.
- [ ] KB upload: file → chunk → embed → `kb_chunks`; expose for A's `/kb/upload` route.
- [ ] Resend `send_email`: verified sender, send a real test email to a team address.
- [ ] `process_refund` mock: write a `refunds` row + audit entry.
- [ ] Analytics queries (totals, escalation rate, avg steps).

**Expected commits:** `feat: supabase schema + seed data` · `feat: crm lookup tools` · `feat: gemini embeddings + pgvector retrieve`
· `feat: kb upload ingest pipeline` · `feat: resend send_email` · `feat: process_refund mock + audit`
· `feat: search_past_tickets + create_bug_report` · `feat: analytics queries`.

**Deliverables:** all 9 tools callable in isolation; real email sends; live KB ingestion; seeded DB.

---

### Member C — Frontend, Evaluation & Demo Lead (the face & the proof)

**Mission:** own the Next.js product, the human-in-the-loop UI, the **brain reasoning trace** view,
the evaluation suite, and the demo.

**Responsibilities**
- Next.js app + Tailwind; Supabase Auth (login, agent/admin roles).
- Ticket **inbox** + **detail** page; render classification badges, cited sources, draft, QA flags.
- The **brain reasoning trace** view (the scratchpad: "looked up order → found duplicate → proposing
  refund") — a standout demo asset.
- The **HITL approval UI**: Approve / Edit & Approve / Escalate / Approve refund / Reject → calls
  `/tickets/{id}/decision`.
- Admin: KB upload UI; analytics dashboard.
- Evaluation suite (≥5 cases) asserting on **tool-selection traces** + final outcome, with a
  low-temperature/seeded brain for reproducibility. Demo script.

**Files owned:** `frontend/` (whole app), `frontend/lib/{api.ts,supabase.ts}`, `backend/tests/`
(eval), `docs/demo_script.md`.

**Task checklist**
- [ ] Read & co-sign the 3 contracts; generate a typed API client from `openapi.yaml`.
- [ ] Build UI against `contracts/fixtures/*.json` (no backend needed day 1).
- [ ] Supabase Auth login + role-gated routes.
- [ ] Inbox list (`GET /tickets`); detail page (`GET /tickets/{id}` + `/trace`).
- [ ] Reasoning-trace component (renders `TraceStep[]`).
- [ ] Approval panel → `POST /decision` with all 5 actions.
- [ ] Admin KB upload form → `/kb/upload`; analytics dashboard → `/analytics`.
- [ ] Eval suite: the 5 scenarios in §7 with assertions; deterministic brain config.
- [ ] `docs/demo_script.md` + rehearse.

**Expected commits:** `feat: next.js scaffold + tailwind` · `feat: supabase auth + role routes` · `feat: ticket inbox`
· `feat: ticket detail + reasoning trace` · `feat: HITL approval panel` · `feat: admin kb upload UI`
· `feat: analytics dashboard` · `test: 5 eval scenarios` · `docs: demo script`.

**Deliverables:** full UI (fixtures → live), green eval suite, demo walkthrough.

---

## 7. Evaluation Plan (≥5 cases — rubric requirement)

Each asserts on the **brain's tool selection** and the **final outcome**. Run the brain at low
temperature / fixed config for reproducibility; mock the LLM with recorded responses where needed.

| # | Scenario | Expected tool path | Expected outcome |
|---|---|---|---|
| 1 | Duplicate charge (billing) | lookup_customer → lookup_order → process_refund★ → draft → send★ | refund proposed, **HITL pause**, email after approval |
| 2 | Known bug | search_past_tickets → retrieve_kb → draft → send★ | grounded workaround, no refund |
| 3 | Unknown bug | search_past_tickets → create_bug_report → draft → send★ | bug filed, ack reply |
| 4 | Vague ticket | request_more_info → pause | **pauses for info**, no premature action |
| 5 | Out-of-scope ("write my homework") | (none) | **refuse** politely, in_scope=false |
| 6 | Refund + cancellation (policy) | check_subscription_status → process_refund★ → escalate | **escalated** per policy, HITL |
| 7 | KB miss (low grounding) | retrieve_kb → (has_grounding=false) → escalate | **no hallucination**, escalate |

★ = high-impact, requires human approval.

**Debugging / failure-analysis story (for the slides):** capture one real bug you find (e.g. the
brain looping, or selecting an invalid tool, or hallucinating on a KB miss) and show how the
guardrail (step budget / allow-list / grounding threshold) fixed it. This directly earns the
*Evaluation & debugging (10%)* marks.

---

## 8. Git & Parallel-Dev Strategy

- **`main`** always-runnable.
- **Hour 1:** branch `setup/contracts` → all three read/agree/commit `contracts/` + empty stubs +
  `requirements.txt` → merge to `main`. **Everyone branches from here.**
- Feature branches: `feat/backend-agents` (A), `feat/data-rag-integrations` (B), `feat/frontend-eval` (C).
- **Integration checkpoint (Milestone 2):** stubbed end-to-end runs — real auth + real UI + stub
  tools/agents. Then swap real pieces in.
- **Reduce coordination:** shared `contracts/fixtures/*.json` so A's API, B's data, and C's UI all
  test against identical payloads. Mock the LLM in eval for determinism.
- **Merge safely:** vertical file ownership ⇒ conflicts only possible in `schemas.py` /
  `requirements.txt` (rare, append-only). Small PRs; run tests before merge.

### Dependency map

```
contracts/  (Hour 1 — briefly blocks all; do FIRST)
   │
   ├─► A  backend: supervisor brain + agents + graph + API   ── critical path
   ├─► B  data: schema + 9 tools + RAG + email + analytics
   └─► C  frontend: UI + reasoning trace + approval + eval
A calls B's tools via tools/registry.py (stub → real at Milestone 2).
C calls A's API via openapi.yaml (fixtures → real at Milestone 2).
B & C never depend on each other directly. Longest pole = A's HITL loop → prototype it early.
```

### Milestones (time-agnostic; gate each before moving on)

1. **Contracts signed & merged** — `contracts/` on `main`, everyone branched.
2. **Stubbed end-to-end** — login works, UI renders fixtures, brain loops on stub tools, HITL pause
   visible.
3. **Real integration** — Gemini brain + real tools + RAG + Resend + KB upload wired; eval green.
4. **Polish & ship** — LangSmith, analytics, deploy (Vercel + Render + Supabase), demo rehearsed,
   README + diagram + individual-contribution docs.

---

## 9. Rubric Mapping (how each requirement is satisfied)

| Rubric criterion | Weight | Covered by |
|---|---|---|
| Problem selection & clarity | 10% | §1, §2 — varied real support, clearly motivated |
| **Multi-agent architecture** | 20% | §3 — governed supervisor brain + 9 tools + 3 LLM agents |
| LangGraph implementation | 15% | supervisor loop, conditional edges, Postgres checkpointer, structured `Decision` |
| Tool use & integrations | 10% | 9 tools incl. RAG, real Resend email, mocked refund — all workflow-driven |
| State, memory, context | 10% | `SupportState` + `scratchpad` working memory, persisted traces |
| Evaluation & debugging | 10% | §7 — 7 scenarios + LangSmith traces + a failure-analysis story |
| Guardrails & HITL | 10% | §3.3, §3.4 — step budget, allow-list, refusal, QA/PII/policy, approval gate |
| Demo quality & usability | 10% | Next.js UI, reasoning-trace view, end-to-end on sample tickets |
| Individual contribution | 15% | §6 — clean vertical ownership; each member owns a defensible slice |

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Gemini structured-output drift | Validate against Pydantic + re-prompt once (in `supervisor.py`) |
| Gemini rate limits during demo | Retry/backoff in `get_llm()`; keep `get_llm()` swappable to another provider |
| Brain loops / picks wrong tool | Step budget + allow-list + escalation guardrails (also a debugging story) |
| Live email fails in demo | Resend verified sender tested early; fall back to showing the audit-log "sent" record |
| HF/Vercel cold start | Pre-warm before the demo; keep KB index small enough to load fast |
| Merge conflicts | Vertical ownership + frozen contracts + fixtures |

---

## 11. Per-member individual-contribution doc (for the Google Form)

Each member writes their own, but structure it as: *the slice I owned → key design decisions I made
→ what I implemented (with file/commit pointers) → how it connects to the whole system → what I'd
improve.* Map directly to your section in §6 and your commits in §8.
