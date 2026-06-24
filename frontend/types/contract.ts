// Hand-written TypeScript mirror of the frozen contracts.
// Source of truth: contracts/schemas.py + contracts/openapi.yaml.
// Keep field names + enum string values EXACTLY in sync with those files.
// Owner: Member C.

// ── Closed vocabularies (mirror contracts/schemas.py enums) ──────────────────
export type TicketStatus =
  | "open"
  | "in_progress"
  | "awaiting_human"
  | "resolved"
  | "escalated"
  | "refused";

export type TicketCategory =
  | "billing"
  | "bug"
  | "how_to"
  | "account"
  | "refund"
  | "out_of_scope"
  | "other";

export type Severity = "low" | "medium" | "high" | "critical";

export type Sentiment = "positive" | "neutral" | "negative" | "angry";

export type RouteDecision =
  | "continue"
  | "await_human"
  | "escalate"
  | "refuse"
  | "done";

// The 5 human-in-the-loop actions (POST /tickets/{id}/decision).
export type HumanAction =
  | "approve"
  | "edit_approve"
  | "escalate"
  | "approve_refund"
  | "reject";

export type ToolName =
  | "lookup_customer"
  | "lookup_order"
  | "check_subscription_status"
  | "retrieve_kb"
  | "search_past_tickets"
  | "create_bug_report"
  | "request_more_info"
  | "process_refund" // high-impact → HITL
  | "draft_reply"
  | "send_email" // high-impact → HITL
  | "escalate"
  | "finish";

// Tools that must pause for human approval (mirror HIGH_IMPACT_TOOLS).
export const HIGH_IMPACT_TOOLS: ToolName[] = ["process_refund", "send_email"];

// ── Agent handoff models (mirror contracts/schemas.py) ───────────────────────
export interface Classification {
  category: TicketCategory;
  severity: Severity;
  sentiment: Sentiment;
  confidence: number; // 0..1
  in_scope: boolean;
  summary: string;
}

export interface DraftReply {
  body: string;
  cited_chunk_ids: string[];
  proposed_actions: ToolName[];
}

export interface GuardrailResult {
  passed: boolean;
  pii_detected: boolean;
  policy_violations: string[];
  hallucination_risk: boolean;
  redacted_body: string | null;
  notes: string;
}

// ── API payloads (mirror contracts/openapi.yaml) ─────────────────────────────
export interface TicketSummary {
  id: string;
  subject: string;
  status: TicketStatus;
  category: TicketCategory | null;
  severity: Severity | null;
  created_at: string;
  // present in the fixture/store rows, handy for the inbox:
  sentiment?: Sentiment | null;
  customer_id?: string | null;
}

export interface Ticket {
  id: string;
  customer_id: string | null;
  subject: string;
  body: string;
  status: TicketStatus;
  classification: Classification | null;
  draft: DraftReply | null;
  guardrail_result: GuardrailResult | null;
  awaiting_action: ToolName | null;
  final_reply: string | null;
  escalated: boolean;
  created_at: string;
  // fixtures carry a flat category/severity/sentiment snapshot too:
  category?: TicketCategory | null;
  severity?: Severity | null;
  sentiment?: Sentiment | null;
}

export interface RunResult {
  ticket_id: string;
  route: RouteDecision;
  awaiting_action: ToolName | null;
  draft: DraftReply | null;
  guardrail_result: GuardrailResult | null;
  final_reply: string | null;
  step_count: number;
}

// NOTE: the live stub /trace returns reason="" and args={} — only fixtures
// populate them. UI must degrade gracefully.
export interface TraceStep {
  step: number;
  tool: ToolName | string;
  reason: string;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
  ok: boolean;
}

export interface DecisionRequest {
  action: HumanAction;
  edited_reply?: string | null;
}

export interface KbDocument {
  id: string;
  title: string;
  created_at: string;
}

export interface KbUploadResult {
  document_id: string;
  chunks_indexed: number;
}

export interface Analytics {
  total_tickets: number;
  resolved: number;
  escalated: number;
  refused: number;
  escalation_rate: number;
  avg_steps_per_ticket: number;
  avg_resolution_seconds: number | null;
}

export interface CreateTicketRequest {
  subject: string;
  body: string;
  customer_email?: string | null;
}

export type Role = "agent" | "admin";
