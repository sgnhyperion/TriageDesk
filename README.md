# TriageDesk — AI Support Desk (Multi-Agent, LangGraph)

A real multi-agent AI support desk: a **governed supervisor "brain"** dynamically selects from a
registry of tools to resolve customer tickets (lookups, RAG, refunds, replies), with a **human
approving every high-impact action** (sending email, processing refunds).

> 📄 **New here? Read [`docs/TEAM_ONBOARDING.md`](docs/TEAM_ONBOARDING.md) first.**
> Full technical plan: [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md).
> The interface contracts everything is built against: [`contracts/`](contracts/).

## Stack
FastAPI + LangGraph (Python) · Next.js (frontend) · Supabase (Postgres + Auth + pgvector + Storage)
· Gemini (LLM + embeddings) · Resend (email) · LangSmith (tracing).

## Repo layout
```
contracts/   # FROZEN interface contracts (schemas.py, schema.sql, openapi.yaml) — read first
backend/     # FastAPI + LangGraph brain + tools + RAG (Members A & B)
frontend/    # Next.js app (Member C)
docs/        # onboarding, project plan, demo script
```

## Run the backend (stub — works without any API keys yet)
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
🟡 **Skeleton / stubs.** The structure boots end-to-end on a fake rule-based brain and stub tools so
all three of us can build in parallel. Each `TODO(Member X)` marks where real logic goes. See the
onboarding doc for who owns what.

## Ownership (fill in names)
- **Member A** (____): backend brain, LangGraph, HITL, API — `backend/{supervisor,graph,agents,api}.py`
- **Member B** (____): DB, 9 tools, RAG, email, analytics — `backend/{tools,rag,integrations,db}/`
- **Member C** (____): Next.js UI, approval screen, eval, demo — `frontend/`, `backend/tests/`
