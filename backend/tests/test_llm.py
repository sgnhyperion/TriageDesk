"""
LLM provider-selection tests. Owner: Member A.

Verify get_llm()'s dynamic provider switch (LLM_PROVIDER) and key resolution,
without importing any provider SDK or making a network call.
"""
import pytest

from backend import llm


def test_defaults_to_gemini(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert llm.provider() == "gemini"


def test_provider_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "Anthropic")
    assert llm.provider() == "anthropic"


def test_unavailable_without_a_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm.llm_available() is False


def test_gemini_available_with_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "real-gemini-key")
    assert llm.llm_available() is True


def test_anthropic_uses_its_own_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-should-be-ignored")
    assert llm.llm_available() is False  # gemini key must not satisfy anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "real-anthropic-key")
    assert llm.llm_available() is True


def test_placeholder_key_counts_as_unset(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your-anthropic-api-key")
    assert llm.llm_available() is False


def test_unknown_provider_is_unavailable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert llm.llm_available() is False


def test_get_llm_raises_clearly_without_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        llm.get_llm()
