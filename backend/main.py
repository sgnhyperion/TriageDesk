"""
FastAPI entry point. Owner: Member A.
Run from the repo root:  uvicorn backend.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router

app = FastAPI(title="TriageDesk API", version="0.1.0")

# Allow the Next.js dev server to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"name": "TriageDesk API", "docs": "/docs", "status": "stub"}
