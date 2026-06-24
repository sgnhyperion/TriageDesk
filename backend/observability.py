"""
LangSmith tracing setup. Owner: Member A.

LangChain/LangGraph emit traces to LangSmith automatically when the tracing env
vars are set. This module normalizes those vars (so either the LANGSMITH_* or the
older LANGCHAIN_* names work) and is a no-op when no key is configured — so the
skeleton runs untraced with zero setup.
"""
import os

_PLACEHOLDER_KEYS = {"", "your-langsmith-key"}


def _api_key() -> str | None:
    key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    return None if (key or "") in _PLACEHOLDER_KEYS else key


def langsmith_enabled() -> bool:
    return _api_key() is not None


def setup_tracing() -> bool:
    """Turn on LangSmith tracing if a key is configured. Returns whether it was enabled."""
    key = _api_key()
    if key is None:
        return False

    project = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or "triagedesk"
    # Set both the modern and legacy env names so any langchain version picks it up.
    os.environ["LANGCHAIN_API_KEY"] = key
    os.environ["LANGSMITH_API_KEY"] = key
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project
    os.environ["LANGSMITH_PROJECT"] = project
    return True
