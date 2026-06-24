you # TriageDesk — Individual Contributions

**Project:** TriageDesk — a governed multi-agent AI support desk (LangGraph + FastAPI + Next.js)
**Course:** Multi-Agent Orchestration [AI/ML] — Capstone
**Repository:** *(paste the GitHub repo URL here)*

**Team**

| Part | Member | Roll number | Slice |
|---|---|---|---|
| A | Harsh Kumar | 10116 | Backend & Agents — the brain, LangGraph, API |
| B | Aman Yadav | 10055 | Data, RAG, tools, email, analytics |
| C | Harsh Kumar | 10098 | Frontend, evaluation suite, demo |

> **One-paragraph product summary.** TriageDesk is an AI customer-support desk. A support agent logs
> in, a ticket arrives, and a *governed supervisor "brain"* (LangGraph) decides — step by step, at
> runtime — which of 9 tools to use to resolve it (look up the customer/order, search the knowledge
> base via RAG, search past tickets, file a bug, propose a refund, draft a reply, send the email).
> Every high-impact action (processing a refund, sending an email) pauses for a human to approve.
> It is genuinely multi-agent (supervisor + triage + resolution + QA agents), governed by guardrails
> (step budget, tool allow-list, scope refusal, PII/policy checks), grounded by RAG, observable via
> LangSmith, and human-in-the-loop on everything risky.

---

# Part A — Backend & Agents (the Brain)

**Name:** Harsh Kumar  **Roll number:** 10116  **Role:** Member A — Backend & Agents Lead

## 1. The slice I owned

I owned the **AI "brain" and the entire backend orchestration layer** — the part that actually
decides what to do with a ticket:

- The **supervisor brain**: the dynamic decision loop that picks one tool at a time, runs it, reads
  the result, and decides again — until resolved, escalated, refused, or paused for a human.
- The **3 LLM agents**: `triage` (classify), `resolution` (draft the reply), `qa_review`
  (PII / policy / hallucination check).
- The **LangGraph graph**: a real `StateGraph` with conditional edges, a Postgres checkpointer, and
  `interrupt()`/resume for human-in-the-loop.
- The **guardrails** that make the brain *governed*.
- The **FastAPI API surface**, **auth** (Supabase JWT + admin gating), **LangSmith** tracing, and the
  **LLM provider factory** (Gemini *or* Claude, swappable in one line).

## 2. Key design decisions I made

- **A governed *dynamic* supervisor, not a fixed pipeline.** With ~9 heterogeneous tools and
  unpredictable tickets, the next step is only known after the previous tool runs (look up order →
  *duplicate charge* → propose refund). A static graph would have to enumerate every path, so the
  brain selects tools at runtime — inside hard deterministic rails.
- **The LLM decider is injectable** (`run(state, decide=...)`), so the whole loop and every guardrail
  are unit-testable with **no API key**, with a deterministic fallback that degrades gracefully on a
  rate limit / quota error instead of crashing.
- **Single source of truth for behavior.** The Python loop in `supervisor.py` is the reference;
  `graph.py` reuses the same policy + guardrails, so the graph only adds structure, never a copy.
- **Provider-agnostic LLM.** `get_llm()` reads `LLM_PROVIDER` and returns Gemini or Claude behind one
  interface, with structured-output validation + a single re-prompt on malformed output.

## 3. What I implemented (file & commit pointers)

| Area | Files | Commit |
|---|---|---|
| LLM provider factory (Gemini + Claude) | `backend/llm.py` | `feat(llm): dynamic get_llm() provider factory` |
| 3 agents + prompt builders | `backend/agents/{triage,resolution,qa_review}.py`, `backend/prompts.py` | `feat(agents): real triage/resolution/qa agents` |
| Supervisor loop + guardrails + HITL resume | `backend/supervisor.py` | `feat(supervisor): governed brain loop + guardrails + HITL resume` |
| LangGraph graph + Postgres checkpointer | `backend/graph.py`, `backend/checkpointer.py` | `feat(graph): LangGraph StateGraph + Postgres checkpointer (HITL)` |
| Auth (Supabase JWT + admin gating) | `backend/auth.py` | `feat(auth): Supabase JWT validation + admin role gating` |
| Observability (LangSmith) | `backend/observability.py` | `feat(observability): LangSmith tracing setup at startup` |
| API routes via the graph engine | `backend/api/routes.py`, `backend/main.py` | `feat(api): drive routes through the graph engine` |
| Backend test suites | `backend/tests/test_{supervisor,graph,api,auth,observability,resilience,llm}.py` | `test(backend): ... suites` |

**Guardrails I built** (`supervisor.py`): step budget → escalate; enum-validated tool allow-list;
confidence floor + critical-severity → escalate; out-of-scope → polite refusal; QA pass (PII
redaction, else escalate); mandatory HITL before `process_refund` / `send_email`.

## 4. How my part connects to the whole system

The brain calls **Member B's 9 tools** via `tools/registry.py` and consumes their `ToolResult`s into
the shared `SupportState.scratchpad`. My **FastAPI endpoints** (`/tickets`, `/run`, `/trace`,
`/decision`, `/kb/upload`, `/analytics`, `/health`) are exactly the surface **Member C's frontend**
calls (frozen in `contracts/openapi.yaml`). The **HITL pause** (`interrupt()`) surfaces in C's
approval panel; C's Approve/Reject hits `/decision`, which resumes my graph and fires B's email/refund.

## 5. What I'd improve next

Reconcile `supervisor.resume()` into a pure graph `Command` resume; stream the reasoning trace to the
UI live; add token-cost-aware model routing (cheap model for triage, stronger only for drafting).

---

# Part B — Data, RAG & Integrations (the Tools & the World)

**Name:** Aman Yadav  **Roll number:** 10055  **Role:** Member B — Data, RAG & Integrations Lead

## 1. The slice I owned

I owned **everything the brain acts on** — the database, the 9 tools' data backings, the RAG
pipeline, real outbound email, the mocked refund, the audit log, and the analytics queries.

- The **Postgres + pgvector database**: schema apply, local dev env, demo seed data.
- The **9 tools**, each a standalone, unit-testable function returning a `ToolResult`.
- The **RAG pipeline**: Gemini embeddings → pgvector index → `retrieve_kb` with a grounding
  threshold, plus the live **KB document upload** path.
- **Real email** via Resend, the **process_refund** mock, the **audit log**, and the **analytics**
  aggregation queries feeding the admin dashboard.

## 2. Key design decisions I made

- **Provider-agnostic data layer.** All DB access goes through one psycopg pool (`db/client.py`) over
  `DATABASE_URL` — the same code runs against the local pgvector container and a hosted Supabase
  Postgres later; only the connection string changes.
- **Tools are self-contained and independently testable** — each a plain function returning a
  `ToolResult` (per `contracts/schemas.py`), tested without the brain. The most parallelizable slice.
- **Grounding threshold on RAG**, not just retrieval: `retrieve_kb` returns `has_grounding` so the
  brain can escalate on a weak match instead of hallucinating — RAG where it improves grounding.
- **Idempotent, parameterised SQL**: seeds use `ON CONFLICT DO NOTHING`; every query uses psycopg
  `%s` placeholders (no SQL injection).
- **Realistic seed data on purpose** — including a *duplicate charge* order, which drives the headline
  refund-with-approval demo path.

## 3. What I implemented (file & commit pointers)

| Area | Files | Commit |
|---|---|---|
| Local pg+pgvector env + schema apply | `backend/db/local_bootstrap.sql`, `backend/db/apply_schema.py` | `chore: local pg+pgvector dev env + schema apply` |
| DB client + query helpers | `backend/db/client.py`, `backend/db/queries.py` | `feat: psycopg db client + query helpers` |
| Seed demo data | `backend/db/seed.py` | `feat: seed demo data` |
| CRM lookup tools | `backend/tools/crm.py` | `feat: crm lookup tools (customer/order/subscription)` |
| Tickets & bug reports | `backend/tools/tickets.py` | `feat: search_past_tickets + create_bug_report` |
| Refund mock + audit | `backend/tools/refund.py` | `feat: process_refund mock + audit log` |
| Request-more-info | `backend/tools/info.py` | `feat: request_more_info persistence` |
| Gemini embeddings | `backend/rag/embed.py` | `feat: gemini embeddings` |
| KB ingest pipeline | `backend/rag/ingest.py` | `feat: kb ingest pipeline (parse -> chunk -> embed -> index)` |
| pgvector retrieval | `backend/rag/retrieve.py` | `feat: retrieve_kb over pgvector + grounding threshold` |
| Resend email + messages/audit | `backend/integrations/email_resend.py` | `feat: resend send_email (key-guarded) + messages/audit rows` |
| KB upload (local storage) + routes | `backend/rag/ingest.py` | `feat: kb upload (local storage) + wire /kb routes` |
| Analytics aggregation | `backend/analytics.py` | `feat: analytics aggregation queries` |
| Postgres-backed store + trace | `backend/store.py` | `feat: postgres-backed store (tickets + reasoning trace)` |

## 4. How my part connects to the whole system

**Member A's brain** calls my tools through `tools/registry.py` and consumes their `ToolResult`s (I
conform to `contracts/schemas.py`). My tables are the **shared truth** every layer reads: A's
checkpointer/store, C's analytics dashboard, the audit trail behind every high-impact action. The KB
upload path is the back half of C's admin form → A's `/kb/upload` route → my ingest pipeline →
pgvector. My Resend email and refund mock fire *after* a human approves in C's panel and A's graph
resumes.

## 5. What I'd improve next

Move KB file storage to Supabase Storage for deploy; add hybrid retrieval (keyword + vector) + a
re-ranker; replace the refund mock with a sandbox Stripe call behind the same approval gate.

---

# Part C — Frontend, Evaluation & Demo (the Face & the Proof)

**Name:** Harsh Kumar  **Roll number:** 10098  **Role:** Member C — Frontend, Evaluation & Demo Lead

## 1. The slice I owned

I owned the **entire product surface and the proof it works** — the Next.js app, the
human-in-the-loop approval experience, the reasoning-trace view, the evaluation suite, and the demo.

- The full **Next.js (App Router) + Tailwind** app: login, inbox, ticket detail, admin.
- The **reasoning-trace view** — the brain's scratchpad made visible ("looked up order → found
  duplicate → proposing refund"). The standout demo moment.
- The **HITL approval panel**: Approve / Edit & Approve / Escalate / Approve refund / Reject.
- **Admin screens**: KB document upload + analytics dashboard.
- The **evaluation suite** (the rubric's ≥5 scenarios) and the **demo script**.

## 2. Key design decisions I made

- **Build against the frozen contract + fixtures first.** I built the whole UI against
  `contracts/openapi.yaml` and `lib/fixtures/*.json` before the backend was live, so I was never
  blocked — the contract was the shared truth.
- **Demo mode = zero-dependency safety net.** With no Supabase keys / no backend, the UI auto-runs in
  **demo mode** (amber banner): one-click role sign-in + sample tickets from fixtures, so the demo
  stays clickable even if the live backend hiccups during the viva.
- **The trace is the hero.** I made the reasoning trace a first-class timeline with classification
  badges, cited sources, the draft, and QA flags — "show the brain thinking" is what proves this
  isn't a one-prompt chatbot.
- **Role-gated routing.** Agent vs admin roles enforced client-side (`RequireAuth`), mirroring A's
  server-side admin gating, so `/admin` is genuinely protected.
- **Typed API client.** `lib/api.ts` mirrors the OpenAPI shapes so a contract change is a type error,
  not a runtime surprise.

## 3. What I implemented (file pointers)

| Area | Files |
|---|---|
| App shell + routing | `frontend/app/{layout,page}.tsx`, `frontend/components/AppHeader.tsx` |
| Login + auth/session + role gating | `frontend/app/login/page.tsx`, `frontend/lib/{auth.tsx,supabase.ts}`, `frontend/components/RequireAuth.tsx` |
| Inbox + new-ticket form | `frontend/app/inbox/page.tsx`, `frontend/components/NewTicketForm.tsx` |
| Ticket detail | `frontend/app/tickets/[id]/page.tsx` |
| **Reasoning trace** | `frontend/components/ReasoningTrace.tsx` |
| Draft + QA flags + badges | `frontend/components/{DraftCard,GuardrailFlags,Badges}.tsx` |
| **HITL approval panel** | `frontend/components/ApprovalPanel.tsx` |
| Admin: KB upload + analytics | `frontend/app/admin/page.tsx`, `frontend/components/{KbUpload,AnalyticsCards}.tsx` |
| Demo-mode banner | `frontend/components/MockModeBanner.tsx` |
| Typed API client + fixtures | `frontend/lib/api.ts`, `frontend/lib/fixtures/*.json` |
| **Evaluation suite** | `backend/tests/test_eval.py` |
| **Demo script** | `docs/demo_script.md` |

**Main commits:** `Ui complete` (the full frontend), plus the eval scenarios and demo script.

## 4. How my part connects to the whole system

Every screen calls **Member A's API** (frozen in `contracts/openapi.yaml`): `GET /tickets`,
`GET /tickets/{id}` + `/trace`, `POST /run`, `POST /decision`, `/kb/upload`, `/analytics`. The
**Approve button → `POST /decision`** is the human half of the loop: it resumes A's LangGraph, which
fires B's email/refund. The **admin upload form** posts to A's `/kb/upload` → B's ingest pipeline →
pgvector. The **eval suite** asserts on the brain's tool-selection path and final outcome, proving A's
routing/guardrails behave across the scenarios in `PROJECT_PLAN.md §7`.

## 5. What I'd improve next

Enable the remaining eval scenarios against the live brain and re-record demo screenshots/GIFs;
live-stream the reasoning trace (SSE/WebSocket); polish empty/error/loading states.
