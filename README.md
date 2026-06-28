# TriageDesk — AI Support Desk (Multi-Agent, LangGraph)

A real multi-agent AI support desk: a **governed supervisor "brain"** dynamically selects from a
registry of tools to resolve customer tickets (lookups, RAG, refunds, replies), with a **human
approving every high-impact action** (sending email, processing refunds).

> 📄 **How it all fits together (with diagrams): [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).**
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

## Run locally with Docker (recommended)
**Prerequisite:** Docker Desktop running. Docker runs only the **database**; backend + frontend run
on your machine.

**Backend** — one command does everything (venv → deps → `.env` → Docker DB → fresh schema+seed+KB →
live API). Terminal 1:
```bash
./run.sh                  # http://localhost:8000/docs   (./run.sh --keep-db to not wipe the DB)
```

**Frontend** — Terminal 2:
```bash
cd frontend && npm install && npm run dev          # http://localhost:3000
```

That's it. `run.sh` is idempotent (safe to re-run) and needs a Gemini key for the KB-ingest step.

> **Stop:** Ctrl-C the servers + `docker compose down`. **No Docker?** Point `DATABASE_URL` at any
> Postgres+pgvector and run `python -m backend.scripts.setup_db`; with no DB the API still boots and
> tools degrade gracefully. The individual steps `run.sh` automates are in
> [`backend/scripts/setup_db.py`](backend/scripts/setup_db.py).


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
In a second terminal (the backend should be running from the steps above):
```bash
cd frontend
cp .env.local.example .env.local           # first time only — sets API URL (+ optional Supabase)
npm install                                 # first time only
npm run dev                                 # http://localhost:3000
```
> With no Supabase keys in `.env.local`, the UI auto-runs in **demo mode** (one-click sign-in +
> fixture tickets), so you can click through the whole flow even without auth configured.

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
