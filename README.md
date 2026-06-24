# TriageDesk — AI Support Desk (Multi-Agent, LangGraph)

A real multi-agent AI support desk: a **governed supervisor "brain"** dynamically selects from a
registry of tools to resolve customer tickets (lookups, RAG, refunds, replies), with a **human
approving every high-impact action** (sending email, processing refunds).

> 📄 **New here? Read [`docs/TEAM_ONBOARDING.md`](docs/TEAM_ONBOARDING.md) first.**
> Full technical plan: [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md).
> The interface contracts everything is built against: [`contracts/`](contracts/).

## Stack
FastAPI + LangGraph (Python) · Next.js (frontend) · Supabase (Postgres + Auth + pgvector + Storage)
· **Gemini or Claude** (LLM, switchable via `LLM_PROVIDER`) · Gemini embeddings · Resend (email)
· LangSmith (tracing).

## Repo layout
```
contracts/   # FROZEN interface contracts (schemas.py, schema.sql, openapi.yaml) — read first
backend/     # FastAPI + LangGraph brain + tools + RAG (Members A & B)
frontend/    # Next.js app (Member C)
docs/        # onboarding, project plan, demo script
```

## Run the backend
Works **with no API keys** (deterministic fallback brain) and lights up the real LLM the moment a
key is configured — no code change.
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload          # http://localhost:8000/docs
```
Try it:
```bash
curl -X POST http://localhost:8000/tickets/TCK-1003/run        # brain runs, pauses for approval
curl http://localhost:8000/tickets/TCK-1003/trace              # the brain's reasoning trace
curl -X POST http://localhost:8000/tickets/TCK-1003/decision \
     -H 'Content-Type: application/json' -d '{"action":"approve"}'   # human approves -> sends
```

### Configure real mode (optional)
```bash
cp backend/.env.example backend/.env        # then fill in the keys you have
```
`backend/.env` (gitignored) is auto-loaded. Key settings:

| Var | Purpose |
|---|---|
| `LLM_PROVIDER` | `gemini` (free tier) **or** `anthropic` (Claude, pay-as-you-go) — the brain works on either |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini chat; also used for embeddings regardless of provider |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Claude chat (e.g. `claude-haiku-4-5` — fast/cheap; `claude-opus-4-8` is slow here) |
| `DATABASE_URL` | Supabase **session-pooler** URI → real Postgres HITL checkpointer (else in-memory) |
| `SUPABASE_JWT_SECRET` | enables JWT auth on protected routes (unset = open dev mode) |
| `LANGSMITH_API_KEY` | enables LangSmith tracing |

Switch LLM provider any time by editing one line (`LLM_PROVIDER=gemini|anthropic`). Quotas/outages
degrade gracefully — the brain falls back to deterministic behavior instead of crashing.

### Live smoke test
Verifies whatever is configured (real LLM + Postgres + LangSmith) end-to-end through the HITL flow:
```bash
python -m backend.scripts.smoke
```

## Run the frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local           # fill in Supabase + API URL
npm run dev                                 # http://localhost:3000
```

## Run tests (eval suite)
```bash
pytest backend/tests -q
```

## Status
🟢 **Member A (backend brain) — implemented & verified.** Real governed supervisor brain +
guardrails, 3 agents, LangGraph `StateGraph` with `interrupt()`/resume HITL on a Postgres
checkpointer, FastAPI routes, Supabase JWT auth, LangSmith tracing, dynamic Gemini/Claude provider
switching, and graceful LLM fallback. Verified live against Gemini, Claude, and a real Supabase
database.
🟡 **Member B (tools/RAG) & Member C (frontend/eval) — in progress.** The brain runs on stub tools
until B's real tools are wired into `backend/tools/registry.py`; C builds against the live API.

## Ownership
- **Member A** (Harsh): backend brain, LangGraph, HITL, API, auth, observability — `backend/{supervisor,graph,agents,api,auth,observability,llm,prompts}.py`
- **Member B** (____): DB, 9 tools, RAG, email, analytics — `backend/{tools,rag,integrations,db}/`
- **Member C** (____): Next.js UI, approval screen, eval, demo — `frontend/`, `backend/tests/`
