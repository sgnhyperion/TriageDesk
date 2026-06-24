"""
Live smoke test for Member A's backend. Run AFTER filling backend/.env.

    python -m backend.scripts.smoke

What it verifies, based on what's configured (it degrades gracefully):
  - GEMINI_API_KEY   → real Gemini structured-output: triage Classification +
                       a supervisor Decision (proves the LLM path + retry wrapper).
  - DATABASE_URL     → the LangGraph Postgres checkpointer persists the run
                       (otherwise the in-memory saver is used).
  - LANGSMITH_API_KEY→ tracing is enabled (traces show up in your LangSmith project).

It always runs a full ticket through the graph: pause for HITL → approve → done,
printing the reasoned trace.
"""
from contracts.schemas import SAMPLE_STATE, HumanAction
from backend import graph as g, observability
from backend.agents import triage
from backend.checkpointer import postgres_available
from backend.llm import llm_available, provider


def main() -> None:
    print("=== TriageDesk backend smoke test ===")
    print(f"Gemini configured:    {llm_available()}")
    print(f"Postgres configured:  {postgres_available()}")
    print(f"LangSmith tracing:    {observability.setup_tracing()}")
    print(f"Checkpointer:         {type(g.get_checkpointer()).__name__}")
    print()

    state = SAMPLE_STATE.model_copy(deep=True)

    if llm_available():
        print(f"-- Real LLM calls (provider={provider()}) --")
        cls = triage.classify(state)
        print(f"triage.classify -> category={cls.category.value} severity={cls.severity.value} "
              f"in_scope={cls.in_scope} confidence={cls.confidence:.2f}")
        state.classification = cls
    else:
        print("-- No LLM key configured: using deterministic fallback brain --")
        state.classification = triage.classify(state)

    print("\n-- Graph run (HITL) --")
    graph = g.get_graph()
    paused = g.start_run(graph, state)
    print(f"route={paused.route.value} awaiting={paused.awaiting_action} steps={paused.step_count}")
    for s in g.reasoned_trace(graph, state.ticket_id):
        print(f"  [{s['step']}] {s['tool']:<20} reason={s['reason'][:70]!r}")

    if paused.awaiting_action is not None:
        done = g.submit_decision(graph, state.ticket_id, HumanAction.APPROVE)
        print(f"\nafter approve: route={done.route.value} final_reply_set={done.final_reply is not None}")

    print("\nOK ✅")


if __name__ == "__main__":
    main()
