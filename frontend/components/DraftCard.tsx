// The customer-facing draft reply awaiting approval. Owner: Member C.
import type { DraftReply } from "@/types/contract";

export function DraftCard({ draft }: { draft: DraftReply }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        Proposed reply
      </h3>
      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">
        {draft.body}
      </p>

      {draft.cited_chunk_ids.length > 0 && (
        <div className="mt-3">
          <span className="text-xs font-medium text-slate-400">Sources: </span>
          {draft.cited_chunk_ids.map((id) => (
            <span
              key={id}
              className="mr-1 inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600"
            >
              {id}
            </span>
          ))}
        </div>
      )}

      {draft.proposed_actions.length > 0 && (
        <div className="mt-2 text-xs text-slate-400">
          Proposed next: {draft.proposed_actions.join(", ").replace(/_/g, " ")}
        </div>
      )}
    </div>
  );
}
