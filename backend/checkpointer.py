"""
HITL pause/resume via LangGraph's Postgres checkpointer. Owner: Member A.

TODO(Member A):
    from langgraph.checkpoint.postgres import PostgresSaver
    checkpointer = PostgresSaver.from_conn_string(os.environ["DATABASE_URL"])
    checkpointer.setup()   # creates its own tables
    graph = builder.compile(checkpointer=checkpointer, interrupt_before=["tool_executor_high_impact"])

This is what lets the graph pause before send_email/process_refund and resume
when the human submits a decision via POST /tickets/{id}/decision.
"""
