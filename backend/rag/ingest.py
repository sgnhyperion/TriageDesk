"""KB document ingestion (admin upload -> chunk -> embed -> index). Owner: Member B."""


def ingest_document(title: str, file_bytes: bytes, uploaded_by: str | None = None) -> dict:
    """TODO(Member B):
      1. parse the file (txt/pdf) -> text
      2. chunk it (e.g. ~500 tokens, small overlap)
      3. embed chunks (rag/embed.py)
      4. insert into kb_documents + kb_chunks (Supabase)
    Returns {"document_id": ..., "chunks_indexed": N}.
    """
    raise NotImplementedError("TODO(Member B): implement KB ingestion pipeline")
