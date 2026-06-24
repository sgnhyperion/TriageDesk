// Status + classification badges. Owner: Member C. (Presentational — no client hooks.)
import type {
  Classification,
  Severity,
  TicketStatus,
} from "@/types/contract";

const STATUS_STYLES: Record<string, string> = {
  open: "bg-slate-100 text-slate-700",
  in_progress: "bg-blue-100 text-blue-700",
  awaiting_human: "bg-amber-100 text-amber-800",
  resolved: "bg-emerald-100 text-emerald-700",
  escalated: "bg-rose-100 text-rose-700",
  refused: "bg-slate-200 text-slate-600",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  awaiting_human: "Awaiting approval",
  resolved: "Resolved",
  escalated: "Escalated",
  refused: "Refused",
};

export function StatusBadge({ status }: { status: TicketStatus | string }) {
  const cls = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

const SEVERITY_STYLES: Record<Severity, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-rose-100 text-rose-800",
};

function Pill({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      {children}
    </span>
  );
}

export function ClassificationBadges({ c }: { c: Classification }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill className="bg-indigo-100 text-indigo-700">
        {c.category.replace("_", " ")}
      </Pill>
      <Pill className={SEVERITY_STYLES[c.severity]}>{c.severity}</Pill>
      <Pill className="bg-slate-100 text-slate-600">{c.sentiment}</Pill>
      <Pill className="bg-slate-100 text-slate-600">
        {Math.round(c.confidence * 100)}% confident
      </Pill>
      {!c.in_scope && (
        <Pill className="bg-rose-100 text-rose-700">out of scope</Pill>
      )}
    </div>
  );
}
