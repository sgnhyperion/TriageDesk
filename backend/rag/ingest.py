"""KB document ingestion: upload/seed -> parse -> chunk -> embed -> index.
Owner: Member B.

Backs the admin KB upload (POST /kb/upload) and the initial seed of data/kb/.
Chunks are embedded with Gemini and stored in kb_chunks.embedding (vector(768)),
searchable immediately via the match_kb_chunks() SQL function (retrieve.py).

Embeddings are written using a pgvector text literal (`'[...]'::vector`) so we
don't need an extra driver package — psycopg sends the literal, Postgres parses
it into the vector column.
"""
from __future__ import annotations

from pathlib import Path

from backend.db import queries
from backend.rag.embed import embed_texts

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEED_KB_DIR = _REPO_ROOT / "data" / "kb"

# Chunking: word windows with overlap. ~200 words ≈ a paragraph or two — small
# enough to be specific, with overlap so a fact split across a boundary is still
# retrievable.
CHUNK_WORDS = 200
CHUNK_OVERLAP = 40


def parse_file_bytes(file_bytes: bytes, title: str = "") -> str:
    """Extract text from an uploaded file. Handles txt/markdown directly; PDFs if
    `pypdf` is available (optional)."""
    if file_bytes[:5] == b"%PDF-":
        try:
            import io
            from pypdf import PdfReader  # optional dependency
            reader = PdfReader(io.BytesIO(file_bytes))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except ModuleNotFoundError as exc:
            raise RuntimeError("PDF upload needs `pypdf` (pip install pypdf)") from exc
    return file_bytes.decode("utf-8", errors="ignore")


def chunk_text(text: str, max_words: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word-windows."""
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + max_words
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap
    return chunks


def _vector_literal(vec: list[float]) -> str:
    """Format an embedding as a pgvector literal: [0.1,0.2,...]."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def ingest_document(title: str, file_bytes: bytes, uploaded_by: str | None = None,
                    source_path: str | None = None) -> dict:
    """Parse → chunk → embed → insert one document and its chunks.

    Returns {"document_id": ..., "chunks_indexed": N} (matches openapi KbUpload).
    """
    text = parse_file_bytes(file_bytes, title)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError(f"no extractable text in '{title}'")

    embeddings = embed_texts(chunks)

    doc = queries.execute(
        "insert into kb_documents (title, source_path, uploaded_by) "
        "values (%s, %s, %s) returning id",
        (title, source_path, uploaded_by))
    document_id = doc["id"]

    for content, vector in zip(chunks, embeddings):
        queries.execute(
            "insert into kb_chunks (document_id, content, embedding) "
            "values (%s, %s, %s::vector)",
            (document_id, content, _vector_literal(vector)))

    return {"document_id": str(document_id), "chunks_indexed": len(chunks)}


def ingest_seed_kb() -> list[dict]:
    """Ingest the starter docs in data/kb/ (idempotent: skips titles already indexed)."""
    results = []
    for path in sorted(_SEED_KB_DIR.glob("*")):
        if path.suffix.lower() not in {".md", ".txt", ".pdf"}:
            continue
        title = path.stem.replace("_", " ").title()
        if queries.fetch_one("select 1 as x from kb_documents where title = %s", (title,)):
            continue  # already ingested
        res = ingest_document(title, path.read_bytes(), source_path=str(path.relative_to(_REPO_ROOT)))
        results.append({"title": title, **res})
    return results


if __name__ == "__main__":
    for r in ingest_seed_kb():
        print(f"  indexed {r['chunks_indexed']:>2} chunks  <-  {r['title']}")
    print("KB seed ingest complete.")
