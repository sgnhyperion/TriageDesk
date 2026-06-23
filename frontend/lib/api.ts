// Typed client for the backend API (matches contracts/openapi.yaml). Owner: Member C.
// TODO(Member C): add auth header (Supabase JWT) and proper types/error handling.

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const listTickets = () => http<any[]>("/tickets");
export const getTicket = (id: string) => http<any>(`/tickets/${id}`);
export const createTicket = (subject: string, body: string) =>
  http<any>("/tickets", { method: "POST", body: JSON.stringify({ subject, body }) });
export const runTicket = (id: string) => http<any>(`/tickets/${id}/run`, { method: "POST" });
export const getTrace = (id: string) => http<any[]>(`/tickets/${id}/trace`);
export const submitDecision = (id: string, action: string, edited_reply?: string) =>
  http<any>(`/tickets/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ action, edited_reply }),
  });
export const getAnalytics = () => http<any>("/analytics");
