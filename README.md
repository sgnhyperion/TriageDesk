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
The brain works **with no API keys** (deterministic fallback) and lights up the real LLM the moment a
key is configured — no code change. The data layer (tickets, tools, RAG) needs Postgres.
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# 1. Database (Postgres + pgvector) — local dev:
docker compose up -d
cp backend/.env.example backend/.env        # DATABASE_URL already points at the local DB
python backend/db/apply_schema.py           # create the schema
python backend/db/seed.py                    # seed demo customers/orders/tickets
python -c "from backend.rag import ingest; ingest.ingest_seed_kb()"   # index the seed KB (needs GEMINI_API_KEY)

# 2. API
uvicorn backend.main:app --reload            # http://localhost:8000/docs
```
> No Docker? Point `DATABASE_URL` at any Postgres+pgvector (e.g. a Supabase session-pooler URI) and run the same `apply_schema.py` / `seed.py`. With no reachable DB the API still boots and DB-backed tools degrade gracefully.

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

## Run tests
```bash
pytest backend/tests -q                                   # orchestration unit tests (offline)
TRIAGEDESK_TEST_DB="$DATABASE_URL" pytest backend/tests backend/tools/tests backend/rag/tests -q   # full suite (needs DB)
```

## Status
🟢 **Integrated and verified end-to-end.** All three slices are wired together and run as one system:
governed LangGraph supervisor brain + guardrails + HITL (Postgres checkpointer) → 9 Postgres-backed
tools → pgvector RAG → Resend email → analytics → Next.js UI with the reasoning-trace and approval
panel. Verified live: the brain autonomously runs `lookup_customer → lookup_order → process_refund`
on the seeded duplicate-charge ticket, pauses for human approval, and resumes — over real HTTP,
against real Postgres, with the real LLM. **85 backend tests pass** (with the DB); the frontend
builds clean.

Provider/DB are swappable by config: `LLM_PROVIDER=gemini|anthropic`, `DATABASE_URL=local|Supabase`.
Everything degrades gracefully — no key → deterministic brain, no DB → fast-fail tools, no Supabase
→ frontend mock mode + open-auth dev mode.

## Ownership
- **Member A** (Harsh): backend brain, LangGraph, HITL, API, auth, observability — `backend/{supervisor,graph,agents,api,auth,observability,llm,prompts}.py`
- **Member B** (____): DB, 9 tools, RAG, email, analytics — `backend/{tools,rag,integrations,db}/`
- **Member C** (____): Next.js UI, approval screen, eval, demo — `frontend/`, `backend/tests/`
