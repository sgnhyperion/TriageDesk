"use client";
// Ticket inbox. Owner: Member C.
import { useEffect, useState } from "react";
import Link from "next/link";
import { listTickets } from "@/lib/api";
import type { TicketStatus, TicketSummary } from "@/types/contract";
import { StatusBadge } from "@/components/Badges";
import { NewTicketForm } from "@/components/NewTicketForm";
import { RequireAuth } from "@/components/RequireAuth";

const STATUS_FILTERS: (TicketStatus | "all")[] = [
  "all",
  "open",
  "in_progress",
  "awaiting_human",
  "resolved",
  "escalated",
  "refused",
];

function Inbox() {
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [filter, setFilter] = useState<TicketStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);

  async function load(f: TicketStatus | "all") {
    setLoading(true);
    const data = await listTickets(f === "all" ? undefined : f);
    setTickets(data);
    setLoading(false);
  }
  useEffect(() => {
    load(filter);
  }, [filter]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Inbox</h1>
          <p className="text-sm text-slate-500">
            Support tickets routed to the AI brain.
          </p>
        </div>
        <button
          onClick={() => setShowNew((v) => !v)}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
        >
          {showNew ? "Close" : "+ New ticket"}
        </button>
      </div>

      {showNew && (
        <NewTicketForm
          onCreated={() => {
            setShowNew(false);
            load(filter);
          }}
          onCancel={() => setShowNew(false)}
        />
      )}

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition ${
              filter === f
                ? "bg-slate-900 text-white"
                : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100"
            }`}
          >
            {f.replace("_", " ")}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <p className="p-6 text-sm text-slate-400">Loading tickets…</p>
        ) : tickets.length === 0 ? (
          <p className="p-6 text-sm text-slate-400">
            No tickets {filter !== "all" && `with status “${filter}”`}.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {tickets.map((t) => (
              <li key={t.id}>
                <Link
                  href={`/tickets/${t.id}`}
                  className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-slate-400">
                        {t.id}
                      </span>
                      {t.category && (
                        <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[11px] font-medium text-indigo-600">
                          {t.category.replace("_", " ")}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-sm font-medium text-slate-900">
                      {t.subject}
                    </p>
                  </div>
                  <StatusBadge status={t.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function InboxPage() {
  return (
    <RequireAuth>
      <Inbox />
    </RequireAuth>
  );
}
