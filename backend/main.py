"""
FastAPI entry point. Owner: Member A.
Run from the repo root:  uvicorn backend.main:app --reload
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.observability import setup_tracing

setup_tracing()  # enables LangSmith tracing iff LANGSMITH_API_KEY is configured

app = FastAPI(title="TriageDesk API", version="0.1.0")

# CORS: allow the Next.js dev server on localhost OR 127.0.0.1 (any port), plus
# any extra origins from CORS_ALLOW_ORIGINS (comma-separated) for deploy (Vercel).
_extra_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_extra_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"name": "TriageDesk API", "docs": "/docs", "status": "stub"}
