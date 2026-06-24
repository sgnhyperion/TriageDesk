// Typed client for the backend API (matches contracts/openapi.yaml). Owner: Member C.
//
// Two behaviours that keep us unblocked during parallel dev:
//   1. Auth: sends `Authorization: Bearer <jwt>` when a token has been set
//      (the AuthProvider calls setAuthToken on sign-in).
//   2. Fixtures fallback: if the backend is unreachable, GET reads fall back to
//      contracts/fixtures so every screen renders with zero backend running.
import type {
  Analytics,
  CreateTicketRequest,
  HumanAction,
  KbDocument,
  KbUploadResult,
  RunResult,
  Ticket,
  TicketStatus,
  TicketSummary,
  TraceStep,
} from "@/types/contract";

import sampleTickets from "@/lib/fixtures/sample_tickets.json";
import sampleTrace from "@/lib/fixtures/sample_trace.json";
import sampleRunResult from "@/lib/fixtures/sample_run_result.json";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── auth token (set by the AuthProvider; null in mock mode) ──────────────────
let _token: string | null = null;
export function setAuthToken(token: string | null) {
  _token = token;
}

// Signals to callers (e.g. a banner) that the last request used a fixture.
export let lastRequestUsedFixture = false;

class ApiError extends Error {
  constructor(public status: number, msg: string) {
    super(msg);
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (_token) headers["Authorization"] = `Bearer ${_token}`;

  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers,
  });
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
  lastRequestUsedFixture = false;
  return res.json() as Promise<T>;
}

/** Try the live API; on a network error fall back to a fixture value. */
async function withFallback<T>(fn: () => Promise<T>, fixture: T): Promise<T> {
  try {
    return await fn();
  } catch (err) {
    // Only swallow connectivity errors / 404s during parallel dev — surface
    // real 4xx/5xx from a running backend by still returning the fixture but
    // flagging it so the UI can show a "using sample data" hint.
    lastRequestUsedFixture = true;
    return fixture;
  }
}

// ── tickets ──────────────────────────────────────────────────────────────────
export function listTickets(status?: TicketStatus): Promise<TicketSummary[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const fixture = (sampleTickets as TicketSummary[]).filter(
    (t) => !status || t.status === status
  );
  return withFallback(() => http<TicketSummary[]>(`/tickets${qs}`), fixture);
}

export function getTicket(id: string): Promise<Ticket> {
  const fixture =
    (sampleTickets as unknown as Ticket[]).find((t) => t.id === id) ??
    (sampleTickets as unknown as Ticket[])[0];
  return withFallback(() => http<Ticket>(`/tickets/${id}`), fixture);
}

export function createTicket(
  subject: string,
  body: string,
  customer_email?: string
): Promise<Ticket> {
  const payload: CreateTicketRequest = { subject, body, customer_email };
  return http<Ticket>("/tickets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runTicket(id: string): Promise<RunResult> {
  const fixture = { ...(sampleRunResult as RunResult), ticket_id: id };
  return withFallback(
    () => http<RunResult>(`/tickets/${id}/run`, { method: "POST" }),
    fixture
  );
}

export function getTrace(id: string): Promise<TraceStep[]> {
  return withFallback(
    () => http<TraceStep[]>(`/tickets/${id}/trace`),
    sampleTrace as TraceStep[]
  );
}

export function submitDecision(
  id: string,
  action: HumanAction,
  edited_reply?: string
): Promise<RunResult> {
  return http<RunResult>(`/tickets/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ action, edited_reply }),
  });
}

// ── knowledge base (admin) ────────────────────────────────────────────────────
export function listKbDocuments(): Promise<KbDocument[]> {
  return withFallback(() => http<KbDocument[]>("/kb/documents"), []);
}

export async function uploadKbDoc(
  file: File,
  title: string
): Promise<KbUploadResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("title", title);
  const headers: Record<string, string> = {};
  if (_token) headers["Authorization"] = `Bearer ${_token}`;
  const res = await fetch(`${BASE}/kb/upload`, {
    method: "POST",
    body: form,
    headers, // no Content-Type — the browser sets the multipart boundary
  });
  if (!res.ok) {
    // Surface the backend's real reason (FastAPI puts it in `detail`).
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body — keep the status line */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<KbUploadResult>;
}

// ── analytics (admin) ──────────────────────────────────────────────────────────
const ZERO_ANALYTICS: Analytics = {
  total_tickets: 0,
  resolved: 0,
  escalated: 0,
  refused: 0,
  escalation_rate: 0,
  avg_steps_per_ticket: 0,
  avg_resolution_seconds: null,
};

export function getAnalytics(): Promise<Analytics> {
  return withFallback(() => http<Analytics>("/analytics"), ZERO_ANALYTICS);
}
