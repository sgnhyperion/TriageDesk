# TriageDesk — Team Onboarding (read this first 🙏)

Hey team 👋 — this is everything you need to understand the project and your role. Read it
end-to-end once. It explains **what we're building, why, how it works, what YOU own, and how we
work together without stepping on each other.** Deeper technical detail lives in
[`docs/PROJECT_PLAN.md`](PROJECT_PLAN.md) and the `contracts/` folder.

---

## 0. TL;DR (60-second version)

We're building **TriageDesk** — a real AI customer-support desk. A support agent logs in, a ticket
comes in, and an **AI "brain" decides on its own which tools to use** to resolve it (look up the
order, search the help docs, file a bug, propose a refund, draft a reply…). **A human approves
before any email is sent or refund is processed.** It's a genuine multi-agent system, not a chatbot.

- **3 of us, 3 clean slices.** Almost zero overlap so we can all build in parallel.
- We agreed on **3 "contract" files first** (the shapes our code exchanges) so our parts fit together.
- Stack: **FastAPI + LangGraph (Python)** backend · **Next.js** frontend · **Supabase** (DB+auth+vectors) · **Gemini** (LLM) · **Resend** (email).

**Who owns what:**

| Role | Owner (fill in name) | One-line job |
|---|---|---|
| **Member A — Backend & Agents** | __________ | The AI brain + the LangGraph + the API |
| **Member B — Data, RAG & Tools** | __________ | The database + the 9 tools + email + RAG |
| **Member C — Frontend, Eval & Demo** | __________ | The Next.js UI + the approval screen + tests + demo |

> 👉 First thing: **put your names in that table** and agree who's A / B / C.

---

## 1. What we're building (in plain English)

Support teams get tons of tickets: "I was charged twice", "the app crashes", "how do I change my
plan?", "refund me now". Handling these by hand is slow; a dumb auto-reply bot is dangerous (it
makes up answers and promises refunds it shouldn't).

**TriageDesk** sits in the middle: an AI reads the ticket and **figures out, step by step, what to
do** — but it can't take any risky action (send a customer email, refund money) without a **human
clicking "Approve"** first. So you get speed *and* safety.

- **Users:** support **agents** (resolve tickets) and **admins** (upload help docs, see analytics).
- **The value:** grounded, policy-checked replies in seconds, with a human in control of anything
  that touches the customer or money.

## 2. Why this needs a *multi-agent* system (our pitch to the evaluators)

This matters — the rubric gives **20% just for the multi-agent architecture** and **10% for problem
clarity**. Our argument has two parts:

1. **Different jobs, different agents.** Understanding a ticket, finding the right info, writing a
   safe reply, and checking that reply are *different skills with different failure modes*. We split
   them into specialized agents so each can be routed, grounded, and guard-railed independently.

2. **Why a dynamic "brain", not a fixed script.** We have **~9 tools**, and *every ticket needs a
   different combination in a different order* — and you often only discover the next step after
   running the previous one (look up order → *oh, it's a duplicate charge* → propose refund). A
   hard-coded flowchart would have to enumerate every possible path = impossible/brittle. So a
   **supervisor "brain" picks the tools at runtime**, like a real support agent would.

That's the whole reason this is a "real" multi-agent product and not a one-prompt chatbot.

## 3. How the system works (the architecture)

```
   Ticket arrives
        │
        ▼
 ┌──────────────────┐     The BRAIN loops: it reads the current state, decides ONE tool
 │  SUPERVISOR BRAIN │◄──┐ to run next (and why), runs it, sees the result, decides again…
 │  picks next tool  │   │ …until it's done, needs a human, or must escalate.
 └────────┬─────────┘   │
          │ chooses one  │
   ┌──────┴───────────────────────────────────────────────────────────┐
   ▼      ▼      ▼      ▼       ▼        ▼          ▼         ▼          ▼
 lookup  lookup  check   search  retrieve  create   request  process   send_email
 customer order  sub     past    KB (RAG)  bug      more     refund ★   ★ (real,
                 status  tickets           report   info     (mock)     Resend)
                                                              │          │
                                              ★ = needs HUMAN APPROVAL before it runs
```

- **The brain's memory** is a running list of "what I did and what I found" (we call it the
  `scratchpad`). Every decision uses it.
- **Guardrails** keep the brain safe: a max number of steps, it can only pick from the allowed tool
  list, low-confidence/refund cases must escalate, out-of-scope tickets get politely refused, and a
  QA check scans every draft for PII/policy issues/hallucination.
- **Human-in-the-loop:** when the brain wants to send an email or process a refund, the system
  **pauses**, the agent sees the draft + reasoning + any warnings, and clicks
  Approve / Edit / Escalate / Reject. Only then does the real action fire.

## 4. The tech stack (and why)

| Part | Tech | Why |
|---|---|---|
| Agent orchestration | **LangGraph (Python)** | The course is about this; best for a supervisor brain + human approval |
| Backend API | **FastAPI** | Runs the brain, exposes a clean API to the frontend |
| AI model + embeddings | **Gemini** | Free tier; one key for both chat and RAG embeddings |
| Frontend | **Next.js + Tailwind** | Real login + nice UI |
| Database + Auth + Vectors + File storage | **Supabase** | One service does it all (Postgres, login, pgvector, uploads) |
| Email | **Resend** | Real outbound email, free, dead simple |
| Tracing/debugging | **LangSmith** | See exactly what the brain did, step by step |

**Real vs. mocked (on purpose):** Real = login, database, RAG, the brain, sending email, KB upload.
Mocked = inbound email (we use a "new ticket" form instead) and refunds (we record the refund
instead of charging a real card). This is an assignment, so we mock the two things that are pure
plumbing and keep everything that scores or demos well.

---

## 5. ⭐ The Contracts — what they are and how YOU use them

**This is the most important section. Read it twice.**

### What a "contract" is
A contract is just **an agreement on the exact shape of data we pass between our code**, written
down in a file *before* we build. Why? Because we work in parallel. If the frontend expects
`ticket.title` but the backend sends `ticket.subject`, it breaks when we connect. Contracts kill
that whole class of bug. We have three:

| File | Describes the shape of… | Matters most to |
|---|---|---|
| [`contracts/schemas.py`](../contracts/schemas.py) | data passed **between the AI agents/tools** (Python/Pydantic) | A ↔ B |
| [`contracts/schema.sql`](../contracts/schema.sql) | the **database tables** in Supabase | B ↔ everyone |
| [`contracts/openapi.yaml`](../contracts/openapi.yaml) | the **API messages** between frontend & backend | A ↔ C |

### How you actually use them while building (THIS is the key part)

You'll mostly be building with AI help (Claude / Cursor / Copilot). **The workflow is: point the AI
at the relevant contract and tell it to conform to it.** Concretely:

- **Member A (backend/agents)** — when building a tool or the brain:
  > *"Read `contracts/schemas.py`. Implement the supervisor so it outputs a `Decision` object, and
  > make every tool return a `ToolResult`. Use `SupportState` as the graph state. Don't change the
  > schema."*

- **Member B (data/tools)** — when building a tool or the DB:
  > *"Read `contracts/schema.sql` and `contracts/schemas.py`. Implement `lookup_order` so it queries
  > the `orders` table and returns a `ToolResult` whose `output` matches what the brain expects."*

- **Member C (frontend)** — when building a screen:
  > *"Read `contracts/openapi.yaml`. Build the ticket-detail page that calls `GET /tickets/{id}` and
  > renders the response. Use `contracts/fixtures/*.json` as mock data until the backend is live."*

So yes — exactly what you guessed: **everyone tells the AI to look at the contracts and build to
them.** The contract is the shared truth that makes three separately-built parts snap together.

### The one rule
If you need to change a shape (add a field, rename something), **edit the contract file, then post
in the group chat: "changed `Decision`, please re-pull."** Never silently change a shape someone
else depends on. That's the whole discipline.

### Why this lets us work in parallel from day one
Because the shapes are fixed, you don't have to wait for each other:
- C builds the entire UI against fake JSON of the agreed shape — no backend needed.
- A builds the brain that produces that shape — no UI needed.
- B builds the tables that store it — independently.
Then we connect, and it fits.

---

## 6. Full folder structure (the whole repo)

```
.                                   # repo root
├── contracts/                      # ⭐ THE AGREEMENTS — read & sign off first (ALL of us)
│   ├── schemas.py                  #   agent/tool data shapes (Pydantic)
│   ├── schema.sql                  #   database tables
│   ├── openapi.yaml                #   frontend↔backend API shapes
│   └── fixtures/                   #   shared sample JSON (so we test on identical data)
│
├── backend/                        # 🅐 MEMBER A + 🅑 MEMBER B live here (Python)
│   ├── main.py                     #   FastAPI app entry                       (A)
│   ├── api/                        #   API route handlers                      (A)
│   ├── graph.py                    #   the LangGraph wiring                     (A)
│   ├── supervisor.py               #   the BRAIN (decision loop + guardrails)   (A)
│   ├── state.py                    #   uses SupportState from contracts         (A)
│   ├── llm.py                      #   get_llm() — Gemini factory               (A)
│   ├── checkpointer.py             #   pause/resume for human approval          (A)
│   ├── agents/                     #   triage / draft_reply / qa_review agents  (A)
│   ├── tools/                      #   the 9 tools                              (B)
│   │   ├── registry.py             #     maps tool name -> function (A+B agree)
│   │   ├── crm.py                  #     lookup_customer/order/subscription     (B)
│   │   ├── tickets.py              #     search_past_tickets, create_bug_report (B)
│   │   ├── refund.py               #     process_refund (mock)                  (B)
│   │   └── info.py                 #     request_more_info                      (B)
│   ├── rag/                        #   retrieve_kb + KB upload/ingest           (B)
│   ├── integrations/email_resend.py#   real email sending                      (B)
│   ├── db/                         #   Supabase client + queries               (B)
│   ├── analytics.py                #   dashboard numbers                       (B)
│   └── tests/                      #   the 5+ eval cases                        (C)
│
├── frontend/                       # 🅒 MEMBER C lives here (Next.js + Tailwind)
│   ├── app/login/                  #   login page (Supabase auth)
│   ├── app/inbox/                  #   ticket list
│   ├── app/tickets/[id]/           #   ticket detail + brain trace + APPROVE buttons
│   ├── app/admin/                  #   KB upload + analytics dashboard
│   ├── lib/api.ts                  #   calls the backend (matches openapi.yaml)
│   └── lib/supabase.ts             #   login/session
│
├── docs/
│   ├── PROJECT_PLAN.md             #   the full technical plan (deeper detail)
│   ├── TEAM_ONBOARDING.md          #   this file
│   └── demo_script.md              #   the demo walkthrough                     (C)
│
├── data/kb/                        #   starter help docs for the KB             (B)
└── README.md                       #   how to set up & run                      (A)

(deps & secrets live with their stack:
   backend/  -> backend/requirements.txt + backend/.env.example
   frontend/ -> frontend/package.json   + frontend/.env.local.example)
```

**Notice:** A and B both live in `backend/` but own *different files* → almost no merge conflicts.
C lives entirely in `frontend/`. The only files we all touch are in `contracts/` (rarely, and by
agreement).

---

## 7. Your role in detail

> Each section is written **to you**. Find your role and read it carefully. Full task checklists,
> expected commits, and deliverables are also in [`PROJECT_PLAN.md` §6](PROJECT_PLAN.md).

### 🅐 Member A — Backend & Agents Lead (the brain)

**Your job:** build the AI brain, wire it in LangGraph, handle the human-approval pause, and expose
the API the frontend calls. You're the heart of the system.

**What you build:**
- `get_llm()` — a function returning a Gemini client (so the model choice lives in one place).
- The **supervisor loop**: read state → ask Gemini for a `Decision` (which tool + why) → run that
  tool → record the result → repeat until done/escalate/budget hit.
- Brain **guardrails**: max steps, only-allowed-tools, escalate on low confidence/refunds, and a
  re-prompt-once if Gemini returns a malformed object.
- The 3 LLM agents: **triage** (classify the ticket), **draft_reply**, **qa_review** (PII/policy/
  hallucination check).
- **Human-in-the-loop**: pause the graph before `send_email`/`process_refund`; resume when the
  human decides.
- The **FastAPI endpoints** from `openapi.yaml` (`/tickets`, `/run`, `/trace`, `/decision`, etc.).
- Turn on **LangSmith** tracing.

**Files you own:** `backend/main.py`, `backend/api/`, `backend/graph.py`, `backend/supervisor.py`,
`backend/state.py`, `backend/llm.py`, `backend/checkpointer.py`, `backend/agents/*`,
`backend/tools/registry.py`, `backend/requirements.txt`, `README.md`.

**Start here:** get the supervisor loop working on **2 fake tools** first (prove the loop), then
swap in B's real tools. Prototype the human-approval pause early — it's the trickiest bit.

**You depend on:** B's tools (you call them) — but you start on stubs, so you're never blocked.

---

### 🅑 Member B — Data, RAG & Tools Lead (the database & the world)

**Your job:** build everything the brain *acts on* — the database, the 9 tools, the knowledge-base
search, real email, and the analytics numbers.

**What you build:**
- The **Supabase database**: run `contracts/schema.sql`, then seed realistic fake data (customers,
  orders — include a duplicate charge!, subscriptions, a few past tickets).
- The **9 tools**, each a standalone function that returns a `ToolResult`:
  `lookup_customer`, `lookup_order`, `check_subscription_status`, `search_past_tickets`,
  `create_bug_report`, `request_more_info`, `process_refund` (mock — writes a refund row).
- **RAG**: turn help docs into Gemini embeddings, store them in pgvector, and build `retrieve_kb`
  (find the most relevant help passages). Plus the **admin KB upload** (upload a doc → it gets
  chunked, embedded, and searchable live).
- **Real email** via Resend (`send_email`).
- **Audit log** writes for every risky action + **analytics** queries for the dashboard.

**Files you own:** `contracts/schema.sql`, `backend/db/`, `backend/tools/{crm,tickets,refund,info}.py`,
`backend/rag/*`, `backend/integrations/email_resend.py`, `backend/analytics.py`, `data/kb/`.

**Start here:** stand up the Supabase project + run the schema + seed data, then build tools one by
one — each is independently testable (call it, check the `ToolResult`). RAG can be built fully on
its own.

**You depend on:** nobody, really — your tools are self-contained. A calls them later via the
registry. This makes you the most parallelizable role.

---

### 🅒 Member C — Frontend, Evaluation & Demo Lead (the face & the proof)

**Your job:** build the entire UI, the all-important human-approval screen, the view that shows the
brain's reasoning, the test suite, and the demo.

**What you build:**
- **Next.js app** + login (Supabase auth, agent vs admin roles).
- **Inbox** (list of tickets) and **ticket detail** page.
- The **reasoning-trace view** — show the brain's steps ("looked up order → found duplicate →
  proposing refund"). This is our coolest demo moment.
- The **approval panel**: Approve / Edit & Approve / Escalate / Approve refund / Reject → calls
  `POST /tickets/{id}/decision`.
- **Admin screens**: KB document upload + analytics dashboard.
- The **evaluation suite** (≥5 test scenarios from `PROJECT_PLAN.md §7`) that checks the brain picks
  the right tools and reaches the right outcome.
- The **demo script** (`docs/demo_script.md`) and rehearsal.

**Files you own:** all of `frontend/`, plus `backend/tests/` (the eval) and `docs/demo_script.md`.

**Start here:** build the whole UI against `contracts/fixtures/*.json` (fake data of the agreed
shape) — you need **zero backend** to start. Swap to the real API once A's endpoints are up.

**You depend on:** A's API shape — but it's frozen in `openapi.yaml`, so you build against that +
fixtures and never wait.

---

## 8. How the three parts connect (integration points)

1. **Frontend → Backend:** C's screens call A's API (shapes in `openapi.yaml`).
2. **Brain → Tools:** A's brain calls B's tools (shapes in `schemas.py`).
3. **Approval:** C's Approve button → A's `/decision` → resumes the brain → real action (B's email/
   refund).
4. **Login:** B sets up Supabase auth; C uses it; A checks the token on API calls.
5. **KB upload:** C's upload form → A's `/kb/upload` route → B's ingest pipeline → pgvector.

**B and C never call each other directly** — they only meet through A's API and the database. That's
intentional: it keeps us decoupled.

## 9. How we work together (git + parallel)

- **`main` always works.** Don't push broken code to it.
- **Hour 1 (all three together):** read the `contracts/` files, agree, commit them, create the
  `fixtures/`. This is the most important 30 minutes — do it on a call together.
- Then each person works on their own branch:
  `feat/backend-agents` (A) · `feat/data-rag-integrations` (B) · `feat/frontend-eval` (C).
- Merge into `main` with small pull requests. Run tests before merging.
- Because we own different files, **merge conflicts will be rare** — only `contracts/` and
  `requirements.txt` are shared, and those change rarely and by agreement.

**Milestones (hit them in order):**
1. Contracts signed & on `main`, everyone branched.
2. Stub end-to-end: login works, UI shows fake data, brain loops on fake tools, approval pause shows.
3. Real integration: Gemini brain + real tools + RAG + email + KB upload all wired; tests pass.
4. Polish: LangSmith, analytics, deploy (Vercel + Render + Supabase), rehearse the demo.

## 10. Getting started (each of you, after Hour 1)

1. Clone the repo, read this doc + `contracts/`.
2. Set up secrets for your stack: backend devs copy `backend/.env.example` → `backend/.env`;
   frontend dev copies `frontend/.env.local.example` → `frontend/.env.local`. Get the keys you need
   (Gemini for A/B; Supabase for all; Resend for B).
3. Create your feature branch.
4. Start on the "Start here" step in your role section above. Build against fixtures/stubs first.

## 11. FAQ

**Q: Do I need the backend running to start my part?**
No. A starts on stub tools; B's tools are standalone; C uses `fixtures/`. That's the point of contracts.

**Q: What if I need to change a shared shape?**
Edit the contract file, tell the group, everyone re-pulls. Never change it silently.

**Q: How do I build fast?** Point your AI tool at the relevant contract file(s) and tell it to
conform to them (see §5 for exact prompts).

**Q: What's the one rubric thing I must protect?** Your **individual contribution (15%)** — make
sure *you* write and commit your slice so you can explain it in the viva. Don't let one person build
everyone's part.

---

Questions → ask in the group chat. Let's build something real. 🚀
