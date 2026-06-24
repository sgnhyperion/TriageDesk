# Individual Contribution — Part C: Frontend, Evaluation & Demo (the Face & the Proof)

**Name:** Harsh Kumar
**Roll number:** 10098
**Role:** Member C — Frontend, Evaluation & Demo Lead
**Project:** TriageDesk — a governed multi-agent AI support desk (LangGraph + FastAPI)
**Repository:** *(paste the GitHub repo URL here)*

---

## 1. The slice I owned

I owned the **entire product surface and the proof it works** — the Next.js app, the
human-in-the-loop approval experience, the brain's reasoning-trace view, the evaluation suite, and
the demo. This is the part evaluators see and click through.

- The full **Next.js (App Router) + Tailwind** app: login, inbox, ticket detail, admin.
- The **reasoning-trace view** — the brain's scratchpad made visible ("looked up order → found
  duplicate → proposing refund"). This is the standout demo moment.
- The **HITL approval panel**: Approve / Edit & Approve / Escalate / Approve refund / Reject.
- **Admin screens**: KB document upload + analytics dashboard.
- The **evaluation suite** (the rubric's ≥5 scenarios) and the **demo script**.

## 2. Key design decisions I made

- **Build against the frozen contract + fixtures first.** I built the whole UI against
  `contracts/openapi.yaml` and `lib/fixtures/*.json` before the backend was live, so I was never
  blocked on Members A/B — the contract was the shared truth.
- **Demo mode = zero-dependency safety net.** With no Supabase keys / no backend, the UI auto-runs in
  **demo mode** (amber banner): one-click role sign-in + sample tickets from fixtures. This means the
  demo stays fully clickable even if the live backend hiccups during the viva — a deliberate risk
  mitigation.
- **The trace is the hero, not an afterthought.** I made the reasoning trace a first-class timeline
  component with classification badges, cited sources, the draft, and QA flags, because "show the
  brain thinking" is what proves this isn't a one-prompt chatbot.
- **Role-gated routing.** Agent vs admin roles are enforced client-side (`RequireAuth`) and mirror
  A's server-side admin gating, so `/admin` is genuinely protected, not cosmetic.
- **Typed API client.** `lib/api.ts` mirrors the OpenAPI shapes so a contract change surfaces as a
  type error, not a runtime surprise.

## 3. What I implemented (file & commit pointers)

| Area | Files |
|---|---|
| App shell + routing | `frontend/app/{layout,page}.tsx`, `frontend/components/AppHeader.tsx` |
| Login + auth/session + role gating | `frontend/app/login/page.tsx`, `frontend/lib/{auth.tsx,supabase.ts}`, `frontend/components/RequireAuth.tsx` |
| Inbox (ticket list) + new-ticket form | `frontend/app/inbox/page.tsx`, `frontend/components/NewTicketForm.tsx` |
| Ticket detail | `frontend/app/tickets/[id]/page.tsx` |
| **Reasoning trace** | `frontend/components/ReasoningTrace.tsx` |
| Draft + QA flags + badges | `frontend/components/{DraftCard,GuardrailFlags,Badges}.tsx` |
| **HITL approval panel** | `frontend/components/ApprovalPanel.tsx` |
| Admin: KB upload + analytics | `frontend/app/admin/page.tsx`, `frontend/components/{KbUpload,AnalyticsCards}.tsx` |
| Demo-mode banner | `frontend/components/MockModeBanner.tsx` |
| Typed API client + fixtures | `frontend/lib/api.ts`, `frontend/lib/fixtures/*.json` |
| **Evaluation suite** | `backend/tests/test_eval.py` (the rubric's scenarios) |
| **Demo script** | `docs/demo_script.md` |

**Main commits:** `Ui complete` (the full frontend), plus the eval scenarios and demo script.

## 4. How my part connects to the whole system

- Every screen calls **Member A's API** (shapes frozen in `contracts/openapi.yaml`): `GET /tickets`,
  `GET /tickets/{id}` + `/trace`, `POST /run`, `POST /decision`, `/kb/upload`, `/analytics`.
- The **Approve button → `POST /decision`** is the human half of the human-in-the-loop loop: it
  resumes A's LangGraph, which then fires B's real email / refund.
- The **admin upload form** posts to A's `/kb/upload`, which runs B's ingest pipeline into pgvector —
  after which a re-run cites the new doc.
- The **eval suite** asserts on the brain's tool-selection path and final outcome, proving A's
  routing/guardrails behave as designed across the scenarios in `PROJECT_PLAN.md §7`.

## 5. What I'd improve next

- Enable the remaining eval scenarios to assert against the live Gemini/Claude brain (some are
  currently skipped pending the real-brain tool paths) and re-record demo screenshots/GIFs.
- Live-stream the reasoning trace as the brain runs (web socket / SSE) instead of after the run.
- Add empty/error/loading states polish and a richer analytics dashboard.
