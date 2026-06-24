"use client";
// Human-in-the-loop approval panel. Owner: Member C.
// Renders the right action set for the paused high-impact tool and calls
// submitDecision(...), then hands the updated RunResult back to the parent.
import { useState } from "react";
import { submitDecision } from "@/lib/api";
import type { DraftReply, HumanAction, RunResult, ToolName } from "@/types/contract";

export function ApprovalPanel({
  ticketId,
  awaitingAction,
  draft,
  onResolved,
}: {
  ticketId: string;
  awaitingAction: ToolName;
  draft: DraftReply | null;
  onResolved: (result: RunResult) => void;
}) {
  const isRefund = awaitingAction === "process_refund";
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState(draft?.body ?? "");
  const [busy, setBusy] = useState<HumanAction | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(action: HumanAction, editedReply?: string) {
    setBusy(action);
    setError(null);
    try {
      const result = await submitDecision(ticketId, action, editedReply);
      onResolved(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  const btn =
    "rounded-lg px-4 py-2 text-sm font-semibold transition disabled:opacity-50";

  return (
    <div className="rounded-lg border-2 border-amber-300 bg-amber-50 p-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-amber-900">
          Action required
        </span>
        <span className="rounded-full bg-amber-200 px-2 py-0.5 font-mono text-xs text-amber-900">
          {awaitingAction.replace(/_/g, " ")}
        </span>
      </div>
      <p className="mt-1 text-sm text-amber-800">
        {isRefund
          ? "The brain wants to process a refund. Approve to execute (mock) and continue."
          : "The brain wants to send this reply to the customer. Approve to send."}
      </p>

      {editing && !isRefund && (
        <textarea
          value={edited}
          onChange={(e) => setEdited(e.target.value)}
          rows={6}
          className="mt-3 w-full rounded-lg border border-slate-300 p-3 text-sm focus:border-slate-500 focus:outline-none"
        />
      )}

      {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}

      <div className="mt-3 flex flex-wrap gap-2">
        {isRefund ? (
          <button
            onClick={() => act("approve_refund")}
            disabled={!!busy}
            className={`${btn} bg-emerald-600 text-white hover:bg-emerald-700`}
          >
            {busy === "approve_refund" ? "Approving…" : "Approve refund"}
          </button>
        ) : editing ? (
          <button
            onClick={() => act("edit_approve", edited)}
            disabled={!!busy || !edited.trim()}
            className={`${btn} bg-emerald-600 text-white hover:bg-emerald-700`}
          >
            {busy === "edit_approve" ? "Saving…" : "Save & approve"}
          </button>
        ) : (
          <>
            <button
              onClick={() => act("approve")}
              disabled={!!busy}
              className={`${btn} bg-emerald-600 text-white hover:bg-emerald-700`}
            >
              {busy === "approve" ? "Approving…" : "Approve"}
            </button>
            <button
              onClick={() => setEditing(true)}
              disabled={!!busy}
              className={`${btn} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`}
            >
              Edit &amp; approve
            </button>
          </>
        )}

        <button
          onClick={() => act("escalate")}
          disabled={!!busy}
          className={`${btn} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`}
        >
          Escalate
        </button>
        <button
          onClick={() => act("reject")}
          disabled={!!busy}
          className={`${btn} border border-rose-300 bg-white text-rose-700 hover:bg-rose-50`}
        >
          Reject
        </button>

        {editing && !isRefund && (
          <button
            onClick={() => setEditing(false)}
            disabled={!!busy}
            className={`${btn} text-slate-500 hover:text-slate-700`}
          >
            Cancel edit
          </button>
        )}
      </div>
    </div>
  );
}
