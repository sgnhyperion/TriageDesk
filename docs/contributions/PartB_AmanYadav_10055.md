# Individual Contribution — Part B: Data, RAG & Integrations (the Tools & the World)

**Name:** Aman Yadav
**Roll number:** 10055
**Role:** Member B — Data, RAG & Integrations Lead
**Project:** TriageDesk — a governed multi-agent AI support desk (LangGraph + FastAPI)
**Repository:** *(paste the GitHub repo URL here)*

---

## 1. The slice I owned

I owned **everything the brain acts on** — the database, the 9 tools' data backings, the RAG
pipeline, real outbound email, the mocked refund, the audit log, and the analytics queries. If the
brain is the decision-maker, my layer is the world it reads from and writes to.

- The **Postgres + pgvector database**: schema apply, local dev env, demo seed data.
- The **9 tools**, each a standalone, unit-testable function returning a `ToolResult`.
- The **RAG pipeline**: Gemini embeddings → pgvector index → `retrieve_kb` with a grounding
  threshold, plus the live **KB document upload** path.
- **Real email** via Resend, the **process_refund** mock, the **audit log**, and the **analytics**
  aggregation queries that feed the admin dashboard.

## 2. Key design decisions I made

- **Provider-agnostic data layer.** All DB access goes through one psycopg connection pool
  (`db/client.py`) over `DATABASE_URL`. The *same* code runs against the local pgvector container
  today and a hosted Supabase Postgres later — only the connection string changes.
- **Tools are self-contained and independently testable.** Each tool is a plain function returning a
  `ToolResult` (per `contracts/schemas.py`), so they can be tested in isolation without the brain —
  which made my slice the most parallelizable.
- **Grounding threshold on RAG**, not just retrieval. `retrieve_kb` returns a `has_grounding` flag so
  the brain can refuse / escalate on a weak match instead of hallucinating — RAG used where it
  improves grounding, exactly as the brief asks.
- **Idempotent, parameterised SQL.** Seeds use `ON CONFLICT DO NOTHING` (safe re-runs); every query
  uses psycopg `%s` placeholders (no string interpolation → no SQL injection).
- **Realistic seed data on purpose** — including a *duplicate charge* order, because that's what
  drives the headline refund-with-approval demo path.

## 3. What I implemented (file & commit pointers)

| Area | Files | Commits |
|---|---|---|
| Local pg+pgvector env + schema apply | `backend/db/local_bootstrap.sql`, `backend/db/apply_schema.py` | `chore: local pg+pgvector dev env + schema apply` |
| DB client + query helpers | `backend/db/client.py`, `backend/db/queries.py` | `feat: psycopg db client + query helpers` |
| Seed demo data | `backend/db/seed.py` | `feat: seed demo data (customers, orders, subscriptions, past tickets)` |
| CRM lookup tools | `backend/tools/crm.py` | `feat: crm lookup tools (customer/order/subscription)` |
| Tickets & bug reports | `backend/tools/tickets.py` | `feat: search_past_tickets + create_bug_report` |
| Refund mock + audit | `backend/tools/refund.py` | `feat: process_refund mock + audit log` |
| Request-more-info | `backend/tools/info.py` | `feat: request_more_info persistence` |
| Gemini embeddings | `backend/rag/embed.py` | `feat: gemini embeddings (get_embeddings + embed.py)` |
| KB ingest pipeline | `backend/rag/ingest.py` | `feat: kb ingest pipeline (parse -> chunk -> embed -> index)` |
| pgvector retrieval | `backend/rag/retrieve.py` | `feat: retrieve_kb over pgvector + grounding threshold` |
| Resend email + messages/audit | `backend/integrations/email_resend.py` | `feat: resend send_email (key-guarded) + messages/audit rows` |
| KB upload (local storage) + routes | `backend/rag/ingest.py`, KB routes | `feat: kb upload (local storage) + wire /kb routes` |
| Analytics aggregation | `backend/analytics.py` | `feat: analytics aggregation queries` |
| Postgres-backed ticket store + trace | `backend/store.py` | `feat: postgres-backed store (tickets + reasoning trace)` |

## 4. How my part connects to the whole system

- **Member A's brain** calls my tools through `tools/registry.py` and consumes their `ToolResult`s —
  I conform to `contracts/schemas.py` so the handoff just fits.
- My `schema.sql` / tables are the **shared truth** every other layer reads: A's checkpointer and
  store, C's analytics dashboard, the audit trail behind every high-impact action.
- The **KB upload** path is the back half of C's admin upload form → A's `/kb/upload` route → my
  ingest pipeline → pgvector, after which `retrieve_kb` can cite the new doc live.
- My **Resend email** and **refund mock** are what actually fire *after* a human approves in C's panel
  and A's graph resumes.

## 5. What I'd improve next

- Move KB file storage from local disk to Supabase Storage for the deployed build.
- Add hybrid retrieval (keyword + vector) and a re-ranker to push grounding quality higher.
- Replace the refund mock with a real (sandbox) Stripe call behind the same approval gate.
