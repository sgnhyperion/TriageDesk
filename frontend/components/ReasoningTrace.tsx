"use client";
// The brain's reasoning trace, rendered as a vertical timeline. Owner: Member C.
// THE standout demo asset. Degrades gracefully: the live stub /trace returns
// reason="" and args={}, so those sections only render when populated.
import { useState } from "react";
import type { ToolName, TraceStep } from "@/types/contract";

const HIGH_IMPACT: ToolName[] = ["process_refund", "send_email"];
const CONTROL: ToolName[] = ["escalate", "finish"];

function toolLabel(tool: string): string {
  return tool.replace(/_/g, " ");
}

function dotColor(step: TraceStep): string {
  if (!step.ok) return "bg-rose-500";
  if (HIGH_IMPACT.includes(step.tool as ToolName)) return "bg-amber-500";
  if (CONTROL.includes(step.tool as ToolName)) return "bg-indigo-500";
  return "bg-emerald-500";
}

function hasKeys(o: Record<string, unknown> | undefined): boolean {
  return !!o && Object.keys(o).length > 0;
}

function StepCard({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const highImpact = HIGH_IMPACT.includes(step.tool as ToolName);

  return (
    <li className="relative pl-8">
      {/* timeline dot */}
      <span
        className={`absolute left-[5px] top-1.5 h-3 w-3 rounded-full ring-4 ring-white ${dotColor(
          step
        )}`}
      />
      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-400">
            #{step.step}
          </span>
          <span className="font-mono text-sm font-medium text-slate-900">
            {toolLabel(step.tool)}
          </span>
          {highImpact && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
              high-impact
            </span>
          )}
          {!step.ok && (
            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-700">
              failed
            </span>
          )}
        </div>

        {step.reason && (
          <p className="mt-1.5 text-sm text-slate-600">{step.reason}</p>
        )}

        {(hasKeys(step.args) || hasKeys(step.result)) && (
          <button
            onClick={() => setOpen((v) => !v)}
            className="mt-2 text-xs font-medium text-slate-400 hover:text-slate-600"
          >
            {open ? "Hide details" : "Show details"}
          </button>
        )}
        {open && (
          <div className="mt-2 space-y-2">
            {hasKeys(step.args) && (
              <pre className="overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600">
                args: {JSON.stringify(step.args, null, 2)}
              </pre>
            )}
            {hasKeys(step.result) && (
              <pre className="overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600">
                result: {JSON.stringify(step.result, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

export function ReasoningTrace({ steps }: { steps: TraceStep[] }) {
  if (!steps.length) {
    return (
      <p className="text-sm text-slate-400">
        No steps yet — run the agent to see its reasoning.
      </p>
    );
  }
  return (
    <ol className="relative space-y-3 border-l border-slate-200">
      {steps.map((s, i) => (
        <StepCard key={`${s.step}-${i}`} step={s} />
      ))}
    </ol>
  );
}
