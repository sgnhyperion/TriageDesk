"""
get_llm() — the single place the LLM provider is chosen. Owner: Member A.

Keeping the provider behind one factory means swapping Gemini -> something else
is a one-line change, and rate-limit retry logic lives in one place.
"""
import os


def get_llm(temperature: float = 0.0):
    """Return a chat model client.

    TODO(Member A): implement with Gemini, e.g.

        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=temperature,
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )

    Use `.with_structured_output(<PydanticModel>)` for Decision/Classification,
    and add a validate-and-retry-once wrapper for malformed outputs.
    """
    raise NotImplementedError("TODO(Member A): wire up Gemini via get_llm()")


def get_embeddings():
    """Return a Gemini embeddings client for RAG (768-dim text-embedding-004).

    Implemented by Member B (RAG depends on it). Kept here so the LLM provider
    lives in one place, consistent with get_llm().
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — copy backend/.env.example to backend/.env "
            "and fill it in (RAG/embeddings need it)."
        )
    return GoogleGenerativeAIEmbeddings(
        model=os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004"),
        google_api_key=api_key,
    )
