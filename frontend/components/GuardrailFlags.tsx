// QA / policy guardrail flags for a draft. Owner: Member C.
import type { GuardrailResult } from "@/types/contract";

function Flag({
  label,
  bad,
}: {
  label: string;
  bad: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
        bad ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
      }`}
    >
      <span aria-hidden>{bad ? "⚠" : "✓"}</span>
      {label}
    </span>
  );
}

export function GuardrailFlags({ g }: { g: GuardrailResult }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          QA &amp; policy check
        </h3>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
            g.passed
              ? "bg-emerald-100 text-emerald-700"
              : "bg-rose-100 text-rose-700"
          }`}
        >
          {g.passed ? "Passed" : "Blocked"}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Flag label="PII" bad={g.pii_detected} />
        <Flag label="Hallucination risk" bad={g.hallucination_risk} />
        <Flag
          label={`Policy (${g.policy_violations.length})`}
          bad={g.policy_violations.length > 0}
        />
      </div>

      {g.policy_violations.length > 0 && (
        <ul className="mt-2 list-inside list-disc text-xs text-rose-600">
          {g.policy_violations.map((v, i) => (
            <li key={i}>{v}</li>
          ))}
        </ul>
      )}

      {g.redacted_body && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-medium text-slate-400">
            Redacted version
          </summary>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
            {g.redacted_body}
          </p>
        </details>
      )}

      {g.notes && <p className="mt-2 text-xs text-slate-500">{g.notes}</p>}
    </div>
  );
}
