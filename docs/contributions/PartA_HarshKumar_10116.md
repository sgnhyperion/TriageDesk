# Individual Contribution — Part A: Backend & Agents (the Brain)

**Name:** Harsh Kumar
**Roll number:** 10116
**Role:** Member A — Backend & Agents Lead
**Project:** TriageDesk — a governed multi-agent AI support desk (LangGraph + FastAPI)
**Repository:** *(paste the GitHub repo URL here)*

---

## 1. The slice I owned

I owned the **AI "brain" and the entire backend orchestration layer** — the part of TriageDesk that
actually decides what to do with a ticket. Concretely:

- The **supervisor brain**: the dynamic decision loop that, per ticket, picks one tool at a time,
  runs it, reads the result, and decides again — until the ticket is resolved, escalated, refused,
  or paused for a human.
- The **3 LLM agents**: `triage` (classify the ticket), `resolution` (draft the reply), and
  `qa_review` (PII / policy / hallucination check).
- The **LangGraph graph**: turning that loop into a real `StateGraph` with conditional edges, a
  Postgres checkpointer, and `interrupt()`/resume for human-in-the-loop.
- The **guardrails** that make the brain *governed* (not a free-for-all).
- The **FastAPI API surface** the frontend calls, plus **auth** (Supabase JWT + admin gating),
  **LangSmith** tracing, and the **LLM provider factory** (Gemini *or* Claude, swappable in one line).

## 2. Key design decisions I made

- **A governed *dynamic* supervisor, not a fixed pipeline.** With ~9 heterogeneous tools and
  unpredictable ticket types, the next step is only known after the previous tool runs (look up
  order → *duplicate charge* → propose refund). A static graph would have to enumerate every path.
  So the brain selects tools at runtime, but inside hard deterministic rails.
- **The LLM decider is injectable** (`run(state, decide=...)`). This let the whole loop and every
  guardrail be unit-tested with **no API key**, and gave a deterministic rule-based fallback so the
  system never crashes on a rate limit / quota error — it degrades gracefully.
- **Single source of truth for behavior.** The plain-Python loop in `supervisor.py` is the reference
  behavior; `graph.py` reuses the same decision policy and guardrails so the graph only adds
  structure (nodes/edges/interrupt), never a second copy of the logic.
- **Provider-agnostic LLM.** `get_llm()` reads `LLM_PROVIDER` and returns Gemini or Claude behind one
  interface, with structured-output validation + a single re-prompt on malformed output.

## 3. What I implemented (file & commit pointers)

| Area | Files | Commits |
|---|---|---|
| LLM provider factory (Gemini + Claude) | `backend/llm.py` | `feat(llm): dynamic get_llm() provider factory` |
| The 3 agents + prompt builders | `backend/agents/{triage,resolution,qa_review}.py`, `backend/prompts.py` | `feat(agents): prompt builders + real triage/resolution/qa agents` |
| Supervisor loop + guardrails + HITL resume | `backend/supervisor.py` | `feat(supervisor): governed brain loop + guardrails + HITL resume` |
| LangGraph graph + Postgres checkpointer | `backend/graph.py`, `backend/checkpointer.py` | `feat(graph): LangGraph StateGraph + Postgres checkpointer (HITL)` |
| Auth (Supabase JWT + admin role gating) | `backend/auth.py` | `feat(auth): Supabase JWT validation + admin role gating` |
| Observability (LangSmith) | `backend/observability.py` | `feat(observability): LangSmith tracing setup at startup` |
| API routes through the graph engine | `backend/api/routes.py`, `backend/main.py` | `feat(api): drive routes through the graph engine` |
| Live smoke test | `backend/scripts/smoke.py` | `feat(scripts): live backend smoke test` |
| Backend test suites | `backend/tests/test_{supervisor,graph,api,auth,observability,resilience,llm}.py` | `test(backend): ... suites` |

**Guardrails I built** (`supervisor.py`): step budget → escalate; tool allow-list (enum-validated
`Decision`); confidence floor + critical-severity → escalate; out-of-scope → polite refusal; QA pass
(PII redaction, else escalate); and mandatory HITL before `process_refund` / `send_email`.

## 4. How my part connects to the whole system

- The brain calls **Member B's 9 tools** through `tools/registry.py` (the dispatch contract) and
  consumes their `ToolResult`s into the shared `SupportState.scratchpad`.
- My **FastAPI endpoints** (`/tickets`, `/run`, `/trace`, `/decision`, `/kb/upload`, `/analytics`,
  `/health`) are exactly the surface **Member C's frontend** calls, frozen in `contracts/openapi.yaml`.
- The **HITL pause** (`interrupt()`) is what surfaces in C's approval panel; C's Approve/Reject hits
  `/decision`, which resumes my graph and fires B's real refund/email.

## 5. What I'd improve next

- Finish reconciling `supervisor.resume()` into a pure graph `Command` resume (currently the
  Python loop is the reference; the graph reproduces it — there's a TODO to unify them fully).
- Add streaming of the reasoning trace to the UI as the brain runs, instead of returning it after.
- Token-cost-aware model routing (cheap model for triage, stronger model only for drafting).
