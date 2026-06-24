"""
Shared pytest fixtures. Owner: Member A.

The test suite must be deterministic and offline regardless of what's in
backend/.env. This autouse fixture clears the LLM / tracing credentials so the
brain and agents use their deterministic stub fallback during tests — live API
verification is done separately via `python -m backend.scripts.smoke`.

Tests that specifically exercise an enabled path (e.g. JWT auth, LangSmith setup)
set the env vars they need inside the test, which overrides this.
"""
import pytest


@pytest.fixture(autouse=True)
def _force_stub_llm(monkeypatch):
    # Clear creds/provider so tests are deterministic + offline (no live LLM / Postgres).
    for var in ("LLM_PROVIDER", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
                "LANGCHAIN_API_KEY", "LANGSMITH_API_KEY", "DATABASE_URL"):
        monkeypatch.delenv(var, raising=False)
    # main.py enables tracing at import from .env; keep the test suite fully offline.
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
