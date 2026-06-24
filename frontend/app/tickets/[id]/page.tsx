"use client";
// Ticket detail + reasoning trace + HITL approval. Owner: Member C.
// The full loop: getTicket -> Run agent -> trace + (if await_human) approval
// panel -> submitDecision -> re-fetch state.
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getTicket, getTrace, runTicket } from "@/lib/api";
import type {
  RouteDecision,
  RunResult,
  Ticket,
  TraceStep,
} from "@/types/contract";
import { ClassificationBadges, StatusBadge } from "@/components/Badges";
import { ReasoningTrace } from "@/components/ReasoningTrace";
import { DraftCard } from "@/components/DraftCard";
import { GuardrailFlags } from "@/components/GuardrailFlags";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { RequireAuth } from "@/components/RequireAuth";

function OutcomeBanner({ route }: { route: RouteDecision }) {
  const map: Record<string, { cls: string; text: string }> = {
    done: {
      cls: "border-emerald-300 bg-emerald-50 text-emerald-800",
      text: "Resolved — reply sent to the customer.",
    },
    escalate: {
      cls: "border-rose-300 bg-rose-50 text-rose-800",
      text: "Escalated to a human agent.",
    },
    refuse: {
      cls: "border-slate-300 bg-slate-50 text-slate-700",
      text: "Refused — this request is out of scope.",
    },
  };
  const m = map[route];
  if (!m) return null;
  return (
    <div className={`rounded-lg border-2 p-4 text-sm font-medium ${m.cls}`}>
      {m.text}
    </div>
  );
}

function TicketDetail({ id }: { id: string }) {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [run, setRun] = useState<RunResult | null>(null);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const [t, tr] = await Promise.all([getTicket(id), getTrace(id).catch(() => [])]);
    setTicket(t);
    setTrace(tr);
    setLoading(false);
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function onRun() {
    setRunning(true);
    try {
      const result = await runTicket(id);
      setRun(result);
      setTrace(await getTrace(id).catch(() => []));
    } finally {
      setRunning(false);
    }
  }

  // After a HITL decision: take the fresh RunResult and re-pull trace + ticket.
  async function onResolved(result: RunResult) {
    setRun(result);
    setTrace(await getTrace(id).catch(() => []));
    setTicket(await getTicket(id).catch(() => ticket as Ticket));
  }

  if (loading || !ticket) {
    return <p className="text-sm text-slate-400">Loading ticket…</p>;
  }

  const awaiting = run?.route === "await_human" && run.awaiting_action;
  const draft = run?.draft ?? ticket.draft;
  const guardrail = run?.guardrail_result ?? ticket.guardrail_result;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/inbox"
          className="text-sm text-slate-400 hover:text-slate-600"
        >
          ← Inbox
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">
            {ticket.subject}
          </h1>
          <StatusBadge status={ticket.status} />
          <span className="font-mono text-xs text-slate-400">{ticket.id}</span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* left: the request + classification */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Customer message
            </h2>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">
              {ticket.body}
            </p>
          </div>

          {ticket.classification && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Classification
              </h2>
              <div className="mt-2">
                <ClassificationBadges c={ticket.classification} />
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {ticket.classification.summary}
              </p>
            </div>
          )}

          <button
            onClick={onRun}
            disabled={running}
            className="w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
          >
            {running ? "Running agent…" : "▶ Run agent"}
          </button>

          {run && <OutcomeBanner route={run.route} />}
        </div>

        {/* right: the brain's work */}
        <div className="space-y-4">
          <div>
            <h2 className="mb-3 text-sm font-semibold text-slate-900">
              Reasoning trace
            </h2>
            <ReasoningTrace steps={trace} />
          </div>

          {draft && <DraftCard draft={draft} />}
          {guardrail && <GuardrailFlags g={guardrail} />}

          {awaiting && (
            <ApprovalPanel
              ticketId={id}
              awaitingAction={awaiting}
              draft={draft}
              onResolved={onResolved}
            />
          )}

          {run?.final_reply && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                Sent reply
              </h3>
              <p className="mt-1 whitespace-pre-wrap text-sm text-emerald-900">
                {run.final_reply}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TicketDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <RequireAuth>
      <TicketDetail id={params.id} />
    </RequireAuth>
  );
}
