"""
LLM resilience tests. Owner: Member A.

The brain/agents must degrade to deterministic behavior when Gemini is
unavailable or errors (quota / 503), never crash the run. (Important for a
free-tier key that intermittently 503s.)
"""
from contracts.schemas import Classification, Decision, SupportState, ToolName
from backend import llm
from backend.agents import triage


def _raise(*_a, **_k):
    raise RuntimeError("503 UNAVAILABLE")


def test_structured_or_uses_fallback_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sentinel = Decision(next_tool=ToolName.FINISH, reason="fallback")
    assert llm.structured_or(Decision, [], lambda: sentinel) is sentinel


def test_structured_or_falls_back_on_llm_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "real-looking-key")  # llm_available() -> True
    monkeypatch.setattr(llm, "structured", _raise)
    sentinel = Decision(next_tool=ToolName.FINISH, reason="fallback")
    assert llm.structured_or(Decision, [], lambda: sentinel) is sentinel


def test_agent_degrades_to_stub_on_llm_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "real-looking-key")
    monkeypatch.setattr(llm, "structured", _raise)
    state = SupportState(ticket_id="T", ticket_subject="Charged twice", ticket_body="help")
    cls = triage.classify(state)
    assert isinstance(cls, Classification)  # fell back instead of raising
    assert cls.in_scope is True
