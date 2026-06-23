# TriageDesk — Context & Decision Log

> Purpose: this file captures the **"why"** behind the project's design — the
> reasoning, alternatives we rejected, and the current state — so any future
> session, teammate, or AI assistant inherits the *decisions*, not just the result.
> The other docs (`PROJECT_PLAN.md`, `TEAM_ONBOARDING.md`, `contracts/`) state
> *what* we're building; this one explains *why we chose it*.

---

## 1. What this project is

A team capstone for the course **Multi-Agent Orchestration [AI/ML]**: build a real,
demo-ready multi-agent AI product (not a chatbot, not a one-prompt app) with ≥3
specialized agents, tools, shared state, conditional routing, RAG, evaluation,
guardrails, observability, and human-in-the-loop on high-impact actions.

We chose **TriageDesk** — an AI customer-support desk. A support agent logs in,
tickets arrive, a governed "supervisor brain" dynamically picks tools to resolve
each ticket, and a human approves every high-impact action (sending email,
processing refunds).

**Team:** 3 developers. **Roles:** A = Backend & Agents, B = Data/RAG/Tools,
C = Frontend/Eval/Demo (see `TEAM_ONBOARDING.md`).

---

## 2. Key decisions and WHY (the part other docs don't justify)

### Why a customer-support desk (over research-gen, resume-tailoring, contract-review)
Support maps onto *every* rubric line with zero stretching: 3+ obviously-distinct
agent roles, natural RAG (help docs), natural HITL (approve before replying), real
conditional routing (resolve vs escalate vs refuse), and meaningful tools. It also
has the highest completion confidence and needs no flaky external dependency at
demo time. It was the best balance of score, demo value, and low risk.

### Why a *dynamic supervisor brain*, not a fixed LangGraph pipeline
This was a deliberate, debated choice. A fixed pipeline (classify→retrieve→draft→
review→send) would actually be *simpler and more reliable* — but for our scoped
problem a brain wasn't strictly *required*, and an evaluator would call that out.
So we **broadened the product** to make the brain genuinely necessary: with ~9
heterogeneous tools and unpredictable ticket types, the set/order/number of steps
can't be known in advance (you discover the next step from the last tool's result).
A static graph would have to enumerate every path combination — intractable and
brittle. Hence a supervisor that selects tools at runtime. **It's governed**, not a
free-for-all: step budget, tool allow-list, confidence/severity escalation,
mandatory HITL before high-impact tools. (We considered a "hybrid" — brain for
resolution, hard rails for safety — and the governed-brain we built is effectively
that: dynamic where it helps, deterministic guardrails where it's risky.)

### Why these 9 tools
`lookup_customer`, `lookup_order`, `check_subscription_status`, `retrieve_kb`,
`search_past_tickets`, `create_bug_report`, `request_more_info`, `process_refund`,
`send_email` (+ control: `escalate`, `finish`). They were chosen specifically so
that *different tickets need different subsets in different orders* — which is what
justifies the dynamic brain. A leaner 5-6 set was considered; we kept the full ~9
for the strongest architecture story.

### Why "real product" but with two intentional mocks
The user explicitly wanted a real product, not a fake one. So: real auth, DB, RAG,
agents, outbound email, live KB upload, observability. We mock only the two things
that are pure plumbing cost with no added rubric/demo value:
- **Inbound email** → a "new ticket" form / simulate button (real inbound parsing
  is fiddly webhooks; same demo value without the plumbing).
- **Refunds** → write a `refunds` row instead of calling Stripe (real money/keys
  add risk; the HITL approval flow is identical either way).

### Why this stack
- **LangGraph (Python)** — the course names it (15% of the rubric by name); most
  mature for a supervisor pattern + HITL interrupt/resume.
- **FastAPI** — hosts the graph, gives the frontend a clean OpenAPI contract.
- **Next.js + Supabase** — real login flows + a single service for Postgres + Auth
  + pgvector + Storage (one integration covers data, auth, vectors, file uploads).
- **Gemini** (LLM + `text-embedding-004`) — chosen by the team; free tier, one key
  for chat + embeddings. Kept behind a `get_llm()` factory so swapping providers is
  one line. Caveat noted: Gemini's structured-output adherence is slightly looser,
  so the brain validates against Pydantic and re-prompts once.
- **Resend** — simplest free real outbound email.
- **No Docker** — deploy targets (Vercel / Render-Railway / Supabase) are
  buildpack/managed; Docker would be pure cost, zero rubric score.

### Why the three "frozen contracts"
`contracts/schemas.py` (agent handoffs), `contracts/schema.sql` (DB), and
`contracts/openapi.yaml` (frontend↔backend API) are agreed *first* so 3 people can
build in parallel against stubs/fixtures without blocking each other. The workflow:
point your AI tool at the relevant contract and tell it to conform. Changes to a
contract must be announced, never silent.

### Structural conventions we settled on
"Config lives with the stack it belongs to": backend deps → `backend/requirements.txt`,
backend secrets → `backend/.env.example`; frontend → `frontend/package.json` +
`frontend/.env.local.example` + `frontend/.gitignore`. (We explicitly moved these
out of the repo root — root-level mixing was the wrong call for a two-stack monorepo.)
`backend/__init__.py` auto-loads `backend/.env` so `uvicorn` works from any CWD.

---

## 3. Current state (as of scaffolding)

🟡 **Shared skeleton scaffolded and runs end-to-end on STUBS** (no API keys needed):
- Backend boots: `uvicorn backend.main:app --reload`.
- A fake rule-based brain loops over stub tools, pauses for human approval on
  `send_email`/`process_refund`, escalates out-of-scope tickets, respects the step
  budget, and resumes on a human decision. Verified working.
- Frontend is a thin Next.js scaffold (pages + typed API client stub).
- Every place real logic goes is marked `TODO(Member A/B/C)`.
- `contracts/fixtures/` has sample ticket/run/trace JSON for parallel dev.
- `data/kb/` has seed help docs for RAG.

Nothing real is wired yet (Gemini, Supabase, Resend, LangGraph graph + Postgres
checkpointer are all stubs/placeholders).

---

## 4. Recommended next steps (in order)

1. Each member branches off `main` (`feat/backend-agents`, `feat/data-rag-integrations`,
   `feat/frontend-eval`) — see `TEAM_ONBOARDING.md`.
2. **Member A:** replace the fake decider in `backend/supervisor.py` with a real
   Gemini structured-output (`Decision`) loop + guardrails; then build the real
   LangGraph graph + Postgres checkpointer for HITL (`graph.py`, `checkpointer.py`).
3. **Member B:** run `contracts/schema.sql` on a fresh Supabase project, seed data,
   then implement the 9 tools + RAG ingest/retrieve + Resend, one at a time.
4. **Member C:** build the UI against `openapi.yaml` + fixtures (reasoning-trace
   view + approval panel are the standout pieces), then the eval suite + demo.

---

## 5. Open items / things deliberately not done yet
- `docs/architecture.png` — a slide diagram still to be produced.
- LangSmith tracing, analytics dashboard, deployment — later milestones.
- The eval suite currently has 3 stub tests; expand to the 7 scenarios in
  `PROJECT_PLAN.md §7`.
