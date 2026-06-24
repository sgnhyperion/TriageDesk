"use client";
// Analytics dashboard cards. Owner: Member C.
import { useEffect, useState } from "react";
import { getAnalytics } from "@/lib/api";
import type { Analytics } from "@/types/contract";

function Card({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
    </div>
  );
}

export function AnalyticsCards() {
  const [a, setA] = useState<Analytics | null>(null);

  useEffect(() => {
    getAnalytics().then(setA);
  }, []);

  if (!a) return <p className="text-sm text-slate-400">Loading metrics…</p>;

  const pct = (n: number) => `${Math.round(n * 100)}%`;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      <Card label="Total tickets" value={a.total_tickets} />
      <Card label="Resolved" value={a.resolved} />
      <Card label="Escalated" value={a.escalated} />
      <Card label="Refused" value={a.refused} />
      <Card label="Escalation rate" value={pct(a.escalation_rate)} />
      <Card label="Avg steps / ticket" value={a.avg_steps_per_ticket.toFixed(1)} />
      <Card
        label="Avg resolution"
        value={
          a.avg_resolution_seconds == null
            ? "—"
            : `${Math.round(a.avg_resolution_seconds)}s`
        }
      />
    </div>
  );
}
