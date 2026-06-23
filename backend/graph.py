"""
LangGraph wiring. Owner: Member A.

TODO(Member A): build the real StateGraph here:
  - node: supervisor  (calls the brain -> Decision)
  - node: tool_executor  (dispatches the chosen tool from tools/registry.py)
  - conditional edges from supervisor: continue -> tool_executor,
    await_human -> interrupt(), escalate/refuse/done -> END
  - compile with the Postgres checkpointer (see checkpointer.py) so HITL
    interrupt()/resume works across HTTP requests.

For the *stub* milestone, the runnable loop lives in supervisor.py (no real
LangGraph yet) so the skeleton boots without a Gemini key. Replace it with this
graph once the brain is real.
"""
