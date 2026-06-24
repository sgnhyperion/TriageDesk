"""LangSmith tracing setup tests. Owner: Member A."""
import os

from backend import observability


def test_disabled_without_key(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    assert observability.langsmith_enabled() is False
    assert observability.setup_tracing() is False


def test_enabled_sets_env_when_key_present(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "triagedesk-test")
    assert observability.langsmith_enabled() is True
    assert observability.setup_tracing() is True
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "triagedesk-test"
