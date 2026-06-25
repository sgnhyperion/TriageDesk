# TriageDesk — Architecture (End to End)

This document explains how TriageDesk works, from a customer ticket arriving to a
human approving a refund and the reply going out. It's grounded in the actual
code — every section points at the files that implement it.

> **One-sentence summary:** A *governed supervisor brain* reads a ticket, picks one
> tool at a time from a registry of ~10 tools (lookups, RAG, refund, email…),
> loops until done — and **pauses for a human** before anything that touches money
> or the customer. The loop is a real **LangGraph** graph whose paused state is
> persisted by a **Postgres checkpointer**, so approval can arrive in a separate
> HTTP request, even after a restart.

---

## 1. The big picture

```
                         ┌─────────────────────────────────────────────┐
                         │                FRONTEND                      │
                         │  Next.js (App Router) · React                │
                         │  inbox · reasoning-trace · approval panel ·  │
                         │  admin (analytics + KB upload)               │
                         └───────────────────┬─────────────────────────┘
                                             │  HTTPS + Bearer JWT
                                             │  (lib/api.ts)
                         ┌───────────────────▼─────────────────────────┐
                         │                BACKEND (FastAPI)             │
                         │                                              │
                         │   api/routes.py  ──auth──> auth.py           │
                         │        │                                     │
                         │        ▼                                     │
                         │   THE BRAIN                                  │
                         │   graph.py (LangGraph)  ⇄  supervisor.py     │
                         │     ├─ agents/  triage · resolution · qa     │
                         │     ├─ llm.py   (Gemini | Claude factory)    │
                         │     └─ tools/registry.py  ──> 10 tools       │
                         │              │                               │
                         │   checkpointer.py (HITL persistence)         │
                         └──────┬───────────────┬──────────────┬───────┘
                                │               │              │
                       ┌────────▼───┐   ┌───────▼──────┐  ┌────▼────────┐
                       │  Postgres  │   │   pgvector    │  │   Resend    │
                       │  CRM/tickets│  │  KB embeddings│  │   (email)   │
                       │  + refunds  │  │   (RAG)       │  │             │
                       └────────────┘   └───────────────┘  └─────────────┘
```

Three slices, built against **frozen contracts** so they could be developed in parallel:

| Layer | Where | Owner | What it is |
|---|---|---|---|
| **Contracts** | [`contracts/`](../contracts/) | shared | The frozen interface: `schemas.py` (Pydantic), `schema.sql` (DB), `openapi.yaml` (HTTP). Everything is built against these. |
| **Brain + API** | [`backend/{supervisor,graph,agents,api,auth,llm,prompts,observability}.py`](../backend/) | Member A | The supervisor loop, guardrails, LangGraph graph, HITL, 3 LLM agents, LLM factory, FastAPI surface, auth, tracing. |
| **Data + Tools + RAG** | [`backend/{tools,rag,integrations,db}/`](../backend/) | Member B | Postgres schema/seed, the 10 tools, the RAG pipeline, KB upload, Resend email, refund mock, analytics. |
| **Frontend** | [`frontend/`](../frontend/) | Member C | Next.js UI, reasoning-trace view, approval panel, admin screens, demo mode, eval suite. |

---

## 2. The contracts (the spine)

Everything fits together because all three slices import the same types from
[`contracts/schemas.py`](../contracts/schemas.py). The important ones:

- **`SupportState`** — the single shared state object that flows through the whole
  run (see §4).
- **`Decision`** — the brain's output each step: `next_tool: ToolName` + `args` + `reason`.
  Because `next_tool` is an **enum**, the LLM physically cannot name a tool that
  doesn't exist — invalid output is rejected at parse time (an allow-list guardrail).
- **`ToolResult`** — every tool returns this: `tool`, `ok`, `output`, `error`.
- **`Classification`**, **`DraftReply`**, **`GuardrailResult`** — the structured
  outputs of the three agents.
- **`ToolName`** — the enum of all 10 tools + `FINISH`/`ESCALATE`.
- **`HIGH_IMPACT_TOOLS = {PROCESS_REFUND, SEND_EMAIL}`** — the set that triggers HITL.
- **`RouteDecision`** — `CONTINUE | AWAIT_HUMAN | DONE | ESCALATE | REFUSE`, the graph's
  branching signal.

These Pydantic models *are* the handoff format between agents — the system fits
together by contract, not by convention.

---

## 3. Request lifecycle (what happens when you click "Run agent")

`POST /tickets/{id}/run` → [`routes.py:133`](../backend/api/routes.py#L133):

```
1. store.new_state(ticket)              → build a fresh SupportState
2. triage.classify(state)               → Classification (1 LLM call, structured)
3. _start_run(state)                    → run the LangGraph brain (graph.py)
       └─ loops: supervisor → tools → supervisor → …
       └─ may PAUSE at a high-impact action (interrupt) and return
4. store.save_state(state)              → read model for /trace + detail
5. return RunResult                     → {route, awaiting_action, draft, final_reply, …}
```

If the brain paused, the response has `route: "awaiting_human"` and `awaiting_action:
"process_refund"`. The UI then shows the approval panel. The human's click hits
`POST /tickets/{id}/decision` → `_resume(...)` → the graph resumes the **exact same
run** from where it paused (see §6).

### The HTTP surface ([`routes.py`](../backend/api/routes.py), implements [`openapi.yaml`](../contracts/openapi.yaml))

| Method + path | Auth | Purpose |
|---|---|---|
| `GET /health` | — | liveness |
| `GET /tickets` | user | inbox list |
| `POST /tickets` | user | create a ticket (mock "inbound email") |
| `GET /tickets/{id}` | user | ticket detail + live run state |
| `POST /tickets/{id}/run` | user | **run the brain** |
| `GET /tickets/{id}/trace` | user | the reasoning trace (tool path + reasons) |
| `POST /tickets/{id}/decision` | user | **resume** a paused run (approve/reject/edit) |
| `GET /kb/documents` | admin | list indexed KB docs |
| `POST /kb/upload` | admin | upload + index a KB doc (chunk → embed → pgvector) |
| `GET /analytics` | user | dashboard metrics |

---

## 4. State management — `SupportState` and the scratchpad

One object flows through every step ([`schemas.py` `SupportState`](../contracts/schemas.py)).
Key fields:

- `ticket_id / ticket_subject / ticket_body / customer_id` — the input.
- **`scratchpad: list[ToolResult]`** — **the brain's working memory.** Every tool the
  brain runs appends its result here. Before each decision the brain reads the whole
  scratchpad — this is how it "remembers" that `lookup_order` already found a duplicate.
- `classification` — the triage output.
- `decision` — the most recent `Decision`.
- `draft` / `guardrail_result` — the reply being built + its QA verdict.
- `route` — the current `RouteDecision` (drives graph branching).
- `step_count` / `max_steps=8` — the step-budget guardrail.
- `awaiting_action` / `human_decision` / `edited_reply` — the HITL channel.
- `final_reply` / `escalated` / `refusal_reason` — terminal outcomes.
- `audit_log: list[str]` — human-readable trail of every guardrail and action.

In the LangGraph engine this object **is** the graph state; each node returns only
the channels it changed (`_changes()` in [`graph.py:40`](../backend/graph.py#L40)),
and the checkpointer persists it between steps and across HTTP requests.

---

## 5. The brain: agents, the supervisor loop, and the graph

### 5a. Four agents, distinct responsibilities ([`backend/agents/`](../backend/agents/))

| Agent | File | Job | Output |
|---|---|---|---|
| **Triage** | [`triage.py`](../backend/agents/triage.py) | classify the ticket | `Classification` |
| **Supervisor** | [`supervisor.py`](../backend/supervisor.py) | **the brain** — pick the next tool each step | `Decision` |
| **Resolution** | [`resolution.py`](../backend/agents/resolution.py) | draft the customer reply | `DraftReply` |
| **QA / guardrail** | [`qa_review.py`](../backend/agents/qa_review.py) | check the draft (PII/policy/hallucination) | `GuardrailResult` |

**Important distinction:** the supervisor doesn't "route to one of 3 agents." It picks
a **tool** each step. The agents fire at fixed points instead:
- **Triage** runs once, before the loop ([`routes.py:145`](../backend/api/routes.py#L145)).
- **Resolution** runs when the brain chooses the `draft_reply` tool (that tool is
  backed by the resolution agent — [`registry.py:16`](../backend/tools/registry.py#L16)).
- **QA** runs automatically, by Python, right after every `draft_reply`
  ([`supervisor.py:160`](../backend/supervisor.py#L160)) — not the brain's choice.

This is the **governed brain** idea: the LLM has freedom over *which tool*, Python
controls *the guardrails and where agents plug in*.

### 5b. The supervisor loop ([`supervisor.py`](../backend/supervisor.py))

Each step:
1. `decide(state)` → a `Decision` (the LLM picks `next_tool` + `args` + `reason`).
2. If `FINISH`/`ESCALATE` → terminate. If a **high-impact** tool → pause for HITL.
3. Otherwise `dispatch(tool, args, state)` runs the tool and appends a `ToolResult`
   to the scratchpad.
4. If the tool was `draft_reply`, run the **QA guardrail** on the new draft.
5. Repeat until done / refuse / escalate / await-human / step budget hit.

The decider is **injectable** (`run(state, decide=...)`): with a key set it's the real
LLM brain (`_llm_decide`); with no key it's a deterministic rule-based fallback
(`_fake_decide`) so the whole system — and the eval suite — runs offline.

### 5c. The LangGraph graph ([`graph.py`](../backend/graph.py))

The same loop, expressed as a real `StateGraph` so HITL is a true `interrupt()`/resume:

```
START → supervisor ─┬─(continue)──→ tools ──→ supervisor      (loop)
                    ├─(await_human)→ high_impact               (interrupt! pause here)
                    └─(done/escalate/refuse)→ END
        high_impact ─┬─(refund approved)→ supervisor           (loop continues)
                     └─(sent / rejected)→ END
```

- **Nodes:** `supervisor` (decide + guardrails), `tools` (run one tool), `high_impact`
  (pause for approval, then execute).
- **Conditional edges** (`_route_from_*`) branch on `state.route` — this is the
  routing/branching requirement.
- The graph reuses the *same* decision policy and guardrail functions from
  `supervisor.py`, so there's a single source of truth — the graph only adds
  structure + the real interrupt/resume mechanics.

---

## 6. Human-in-the-loop (HITL) — the headline feature

High-impact tools (`process_refund`, `send_email`) **must** have human approval.

**How the pause survives across two separate HTTP requests:**

1. During a run, the brain decides on `process_refund`. The `high_impact` node calls
   LangGraph's **`interrupt()`** ([`graph.py:104`](../backend/graph.py#L104)).
2. `interrupt()` **persists the entire graph state** via the **checkpointer**, keyed by
   `thread_id = ticket_id`, and returns control to the HTTP handler. The response says
   `awaiting_human`.
3. Later — possibly a different request, possibly after a server restart — the human
   approves: `POST /tickets/{id}/decision`.
4. `submit_decision` calls `graph.invoke(Command(resume={...}))`
   ([`graph.py:285`](../backend/graph.py#L285)). LangGraph reloads the checkpoint by
   `thread_id`, `interrupt()` *returns* the human's payload, and the run continues from
   the exact same point — executing the refund, then drafting and sending.

**The checkpointer** ([`checkpointer.py`](../backend/checkpointer.py)):
- `DATABASE_URL` set → **`PostgresSaver`** (survives restarts, shared across processes).
  This is what creates the `checkpoint_*` tables you see in the DB.
- No DB → **`MemorySaver`** (in-memory) so the skeleton + tests still run HITL.

The plain-Python `supervisor.resume()` mirrors this exact control flow as the tested
fallback when langgraph isn't installed.

---

## 7. Tools — what the brain can *do* ([`backend/tools/`](../backend/tools/) + registry)

All 10 tools share one signature — `fn(args: dict, state) -> ToolResult` — and are
dispatched through [`registry.py`](../backend/tools/registry.py) (`dispatch()`), which
catches any exception so a tool can never crash the brain.

| Tool | File | What it does | Impact |
|---|---|---|---|
| `lookup_customer` | [`crm.py`](../backend/tools/crm.py) | customer + account summary | read |
| `lookup_order` | [`crm.py`](../backend/tools/crm.py) | orders + **detects duplicate charges** | read |
| `check_subscription_status` | [`crm.py`](../backend/tools/crm.py) | plan / status / renewal | read |
| `search_past_tickets` | [`tickets.py`](../backend/tools/tickets.py) | full-text search over resolved tickets | read |
| `retrieve_kb` | [`rag/retrieve.py`](../backend/rag/retrieve.py) | **RAG over pgvector** + grounding check | read |
| `request_more_info` | [`info.py`](../backend/tools/info.py) | record a clarifying question | low |
| `create_bug_report` | [`tickets.py`](../backend/tools/tickets.py) | file a bug (unknown-bug path) | low |
| `draft_reply` | [`registry.py`](../backend/tools/registry.py) → resolution agent | write the reply | low |
| `process_refund` | [`refund.py`](../backend/tools/refund.py) | **mock** refund (DB row + audit) | **HIGH → HITL** |
| `send_email` | [`integrations/email_resend.py`](../backend/integrations/email_resend.py) | **real** outbound email (Resend) | **HIGH → HITL** |

Two things are mocked on purpose: inbound email (a "new ticket" form) and the refund
(writes a `refunds` row + audit entry, no Stripe). The approval flow is identical
either way. `send_email` is key-guarded: with `RESEND_API_KEY` it sends for real;
without it, it records the intent so demos still work — flip the env var, zero code change.

---

## 8. RAG / knowledge grounding ([`backend/rag/`](../backend/rag/))

**Ingest** ([`ingest.py`](../backend/rag/ingest.py)): upload → parse (PDF via `pypdf`,
else UTF-8) → chunk → embed → insert into `kb_chunks`. Exposed live to admins via
`POST /kb/upload`.

**Embed** ([`embed.py`](../backend/rag/embed.py)): Gemini `gemini-embedding-001` at
768 dimensions (used for both ingest and queries, regardless of chat provider).

**Retrieve** ([`retrieve.py`](../backend/rag/retrieve.py)): embed the query → call the
Postgres `match_kb_chunks()` function (cosine similarity over a pgvector `ivfflat`
index) → return the top chunks. **The grounding guardrail:** if the top similarity is
below `GROUNDING_THRESHOLD` (0.58, tuned for these embeddings), `has_grounding=False`
— the brain's signal to **escalate instead of hallucinating** an answer the KB
doesn't support.

---

## 9. The LLM factory — provider-swappable + resilient ([`llm.py`](../backend/llm.py))

- **`LLM_PROVIDER=gemini|anthropic`** — one env var switches the chat model between
  Gemini (`ChatGoogleGenerativeAI`) and Claude (`ChatAnthropic`). The brain works on
  either; embeddings always use Gemini.
- **`structured(Model, messages)`** — forces validated structured output into a
  Pydantic schema (the agent handoff format).
- **`structured_or(Model, messages, fallback)`** — the resilience layer: if the LLM
  errors (quota, 503, rate-limit), it returns a deterministic fallback instead of
  crashing mid-run. Every agent uses this, which is why a free-tier quota hit
  degrades gracefully rather than breaking a demo.

---

## 10. Guardrails — the governance (eight of them)

Deterministic Python around the LLM ([`supervisor.py`](../backend/supervisor.py)):

1. **Allow-list** — `Decision.next_tool` is a `ToolName` enum → invalid tools rejected at parse time.
2. **Out-of-scope → refuse** (`_scope_guardrail`).
3. **Low confidence (< 0.35) → escalate**.
4. **Critical severity → escalate**.
5. **Step budget (max 8) → escalate** — no infinite loops.
6. **Grounding floor** — KB top score < threshold → escalate, no hallucination (§8).
7. **QA / PII pass** on every draft — redact if possible, else escalate (`_run_qa`).
8. **Mandatory human approval** before `process_refund` and `send_email` (§6).

---

## 11. Auth ([`auth.py`](../backend/auth.py))

Dual JWT verification:
- **`SUPABASE_URL`** set → verify the Supabase JWT against the project's **JWKS**
  (ES256/RS256, asymmetric signing keys) via `PyJWKClient`.
- **`SUPABASE_JWT_SECRET`** set → legacy **HS256** verification.
- **Neither** → open **dev mode** (a built-in admin user) so the API runs with zero
  auth config.

Role (`admin`/`agent`) is read from the JWT's `app_metadata`/`user_metadata`. Admin-only
routes (`/kb/*`) use the `require_admin` dependency.

---

## 12. Observability ([`observability.py`](../backend/observability.py))

`setup_tracing()` (called at startup in [`main.py:13`](../backend/main.py#L13)) turns on
**LangSmith** when `LANGSMITH_API_KEY` is set — every LLM call and graph step is traced,
tagged with the ticket id (`run_name`/`tags`/`metadata` in
[`graph.py:206`](../backend/graph.py#L206)). It's a no-op with no key. Beyond LangSmith:
the per-ticket `audit_log`, and `reasoned_trace()` ([`graph.py:242`](../backend/graph.py#L242))
which reconstructs the UI's reasoning trace (tool + reason + args + result, per step)
from the checkpoint history.

---

## 13. Data model ([`contracts/schema.sql`](../contracts/schema.sql))

App tables: `profiles`, `customers`, `orders`, `subscriptions`, `tickets`, `messages`,
`agent_traces`, `bug_reports`, `refunds`, `kb_documents`, `kb_chunks`, `audit_log` —
plus the `match_kb_chunks()` similarity function and the `vector` + `uuid-ossp`
extensions. The LangGraph `checkpoint_*` tables are created separately and
automatically by the checkpointer's `setup()` (§6).

> Note: which database these live in is set by `DATABASE_URL`. Locally that's a Docker
> Postgres (`localhost/triagedesk`); point it at the Supabase pooler to host them there.

---

## 14. Frontend ([`frontend/`](../frontend/))

Next.js (App Router). Two behaviors keep it robust:
- **Typed API client** ([`lib/api.ts`](../frontend/lib/api.ts)) — sends the Bearer JWT;
  on a network error, GET reads fall back to fixtures so screens render even with no
  backend (it flags `lastRequestUsedFixture` so the UI can show a "sample data" hint).
- **Auth** ([`lib/auth.tsx`](../frontend/lib/auth.tsx)) — real Supabase email/password
  sign-in (role from `app_metadata`/`user_metadata`, falling back to a `profiles` row),
  or **demo mode** (one-click role switcher, no keys needed).

Screens: inbox, ticket detail with the **reasoning-trace view**, the **human-approval
panel**, and role-gated **admin** (analytics cards + live KB upload).

---

## 15. Evaluation ([`backend/tests/`](../backend/tests/))

- **11 scenario tests** in [`test_eval.py`](../backend/tests/test_eval.py): each asserts
  on the brain's **tool path** and **final outcome** for a ticket type — duplicate
  charge → refund → pause → approve; known bug → grounded reply, no refund; unknown bug
  → bug report; vague → request info; out-of-scope → refuse; KB miss → escalate (no
  hallucination); plus the guardrail scenarios.
- They're **deterministic**: the decider is injectable, so they test the loop,
  guardrails, and routing — not the LLM's random sampling — and run with no API key in
  under a second.
- **92 tests pass overall** across orchestration, tools, RAG, auth, and API.

---

## 16. End-to-end trace: the duplicate-charge ticket

The headline demo, step by step:

```
POST /tickets/TCK-1001/run
  triage.classify         → billing, medium severity, in_scope, confident
  brain → lookup_customer → {found: true, ...}              (scratchpad +1)
  brain → lookup_order    → {duplicate_charge: true, ...}   (scratchpad +1)
  brain → process_refund  → HIGH-IMPACT → interrupt()  ─────► PAUSE
                             route = awaiting_human, checkpoint persisted
  ── HTTP response: {route: "awaiting_human", awaiting_action: "process_refund"}

[ human clicks Approve in the UI ]

POST /tickets/TCK-1001/decision  {action: "approve_refund"}
  graph resumes from the checkpoint (Command(resume=...))
  process_refund          → refunds row + order marked refunded + audit
  brain → draft_reply     → DraftReply  → QA guardrail passes
  brain → send_email      → HIGH-IMPACT → interrupt()  ─────► PAUSE (approve again)
  [ approve ] → Resend sends → final_reply set → route = done
```

The brain discovered the refund **only after** the lookup (dynamic, not scripted), and
**moved no money without a human** — speed *and* safety, which is the whole thesis.
