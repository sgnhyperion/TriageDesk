"""
get_llm() — the single place the LLM provider is chosen. Owner: Member A.

The provider is selected at runtime by the LLM_PROVIDER env var:
    LLM_PROVIDER=gemini     (default) → Google Gemini  (langchain-google-genai)
    LLM_PROVIDER=anthropic            → Claude         (langchain-anthropic)

Keeping the provider behind this one factory means swapping is a config change,
not a code change — everything downstream (the brain, structured outputs, the
agents) only depends on the LangChain chat interface and works on either.

Imports of the provider SDKs are LAZY (inside the functions) so the backend
imports cleanly even when a provider's optional dependency isn't installed.
Use `llm_available()` to decide whether to call the real model or fall back to a
deterministic stub.
"""
import logging
import os
from typing import Any, Callable, Type, TypeVar

from pydantic import BaseModel, ValidationError

_T = TypeVar("_T", bound=BaseModel)

logger = logging.getLogger(__name__)

# provider -> (env var holding the key, placeholder values that mean "unset")
_PROVIDER_KEY_VAR = {
    "gemini": ("GEMINI_API_KEY", {"", "your-gemini-api-key"}),
    "anthropic": ("ANTHROPIC_API_KEY", {"", "your-anthropic-api-key"}),
}

# Claude models that REJECT a `temperature` param (400). Sampling params were
# removed on the newest Opus/Fable tiers — omit temperature for these.
_ANTHROPIC_NO_TEMPERATURE = ("claude-opus-4-8", "claude-opus-4-7", "claude-fable-5", "claude-mythos")


def provider() -> str:
    """The configured LLM provider (lowercased). Defaults to 'gemini'."""
    return (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()


def _api_key(for_provider: str | None = None) -> str | None:
    p = for_provider or provider()
    var, placeholders = _PROVIDER_KEY_VAR.get(p, (None, set()))
    if var is None:
        return None
    key = os.getenv(var)
    return None if (key or "") in placeholders else key


def llm_available() -> bool:
    """True when the configured provider is known and its API key is set.

    Lets the brain and agents use the real LLM when configured and fall back to
    the deterministic stub otherwise — so the skeleton (and the eval suite) run
    with no key, and the real model kicks in automatically once one is set.
    """
    return provider() in _PROVIDER_KEY_VAR and _api_key() is not None


def get_llm(temperature: float = 0.0):
    """Return a chat model client for the configured provider.

    Use `.with_structured_output(<PydanticModel>)` for Decision/Classification,
    or the `structured()` helper below which adds validate-and-retry-once.
    """
    p = provider()
    key = _api_key(p)
    if key is None:
        var = _PROVIDER_KEY_VAR.get(p, ("<unknown>",))[0]
        raise RuntimeError(
            f"No API key for LLM_PROVIDER={p!r} (set {var} in backend/.env). "
            f"Guard real calls with llm_available() so the skeleton still runs on stubs."
        )

    if p == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=temperature,
            google_api_key=key,
            # Exponential backoff on transient rate limits (429) — see PROJECT_PLAN §10.
            max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "3")),
        )

    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
        kwargs: dict[str, Any] = {}
        # Newest Opus/Fable tiers reject `temperature` (400); Sonnet/Haiku accept it.
        if not any(model.startswith(prefix) for prefix in _ANTHROPIC_NO_TEMPERATURE):
            kwargs["temperature"] = temperature
        return ChatAnthropic(
            model=model,
            api_key=key,
            max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", "3")),
            **kwargs,
        )

    raise RuntimeError(f"Unknown LLM_PROVIDER={p!r}. Supported: 'gemini', 'anthropic'.")


def get_embeddings():
    """Return an embeddings client for RAG (used by Member B's ingest/retrieve).

    Embeddings ALWAYS use Gemini regardless of LLM_PROVIDER — Anthropic has no
    embeddings API, and RAG needs embeddings even when chat runs on Claude.
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    key = _api_key("gemini")
    if key is None:
        raise RuntimeError(
            "GEMINI_API_KEY is required for embeddings (Anthropic has no embeddings API)."
        )
    return GoogleGenerativeAIEmbeddings(
        model=os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004"),
        google_api_key=key,
    )


def structured(model: Type[_T], messages: Any, *, temperature: float = 0.0, retries: int = 1) -> _T:
    """Get a validated `model` instance from the LLM, re-prompting once on malformed output.

    Some providers' structured-output adherence is looser than others, so we
    validate against the Pydantic model and, on failure, append a repair hint and
    try again (default: one retry, per the STACK NOTE in contracts/schemas.py).

    `messages` is anything langchain's `.invoke()` accepts — typically a list of
    (role, content) tuples from backend/prompts.py.
    """
    structured_llm = get_llm(temperature).with_structured_output(model)
    attempt_messages = list(messages)
    last_err: Exception | None = None
    for _ in range(retries + 1):
        try:
            result = structured_llm.invoke(attempt_messages)
            # with_structured_output usually returns the model; be defensive.
            return result if isinstance(result, model) else model.model_validate(result)
        except (ValidationError, ValueError) as err:
            last_err = err
            attempt_messages = list(messages) + [(
                "human",
                f"Your previous response did not match the required schema ({err}). "
                f"Respond again, strictly conforming to the schema.",
            )]
    raise ValueError(f"LLM structured output failed after {retries + 1} attempts: {last_err}")


def structured_or(model: Type[_T], messages: Any, fallback: Callable[[], _T], **kwargs) -> _T:
    """structured(), but degrade to fallback() when the LLM is unavailable or errors.

    Keeps the product working when no key is set OR the model is rate-limited /
    quota-exhausted / overloaded (e.g. 429/503) — the deterministic fallback takes
    over for that step instead of crashing the run (PROJECT_PLAN §10: demo resilience).
    """
    if not llm_available():
        return fallback()
    try:
        return structured(model, messages, **kwargs)
    except Exception as err:  # noqa: BLE001 - any LLM/transport error degrades gracefully
        reason = str(err).split("\n", 1)[0][:140]
        logger.warning("LLM call failed (%s: %s); using deterministic fallback.",
                       type(err).__name__, reason)
        return fallback()
