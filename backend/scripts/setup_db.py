"""One-shot local DB setup: apply schema -> seed -> ingest KB.

Replaces running three scripts by hand:
    python backend/db/apply_schema.py
    python backend/db/seed.py
    python -c "from backend.rag import ingest; ingest.ingest_seed_kb()"

Run from the repo root (Docker Postgres must be up: `docker compose up -d`):
    python -m backend.scripts.setup_db            # set up, skipping schema if it exists
    python -m backend.scripts.setup_db --fresh    # wipe + recreate the DB volume first

If the schema already exists, this continues to seed + ingest instead of failing
(so it is safe to re-run). Use --fresh for a clean rebuild.

Also explicitly closes the psycopg connection pool at the end so the script
exits silently instead of emitting the Python 3.14 `PythonFinalizationError`
that fires when the pool's destructor runs during interpreter shutdown.
"""
import subprocess
import sys

from backend.db.apply_schema import main as apply_schema
from backend.db.client import close_pool
from backend.db.seed import seed_all
from backend.rag.ingest import ingest_seed_kb


def _fresh_volume() -> None:
    print("--fresh: resetting the Docker Postgres volume …")
    subprocess.run(["docker", "compose", "down", "-v"], check=True)
    subprocess.run(["docker", "compose", "up", "-d"], check=True)
    # give Postgres a moment to accept connections
    from backend.db.client import healthcheck

    for _ in range(30):
        if healthcheck():
            return
        subprocess.run(["sleep", "1"])
    sys.exit("Postgres did not become reachable after `docker compose up -d`.")


def main(fresh: bool = False) -> None:
    if fresh:
        _fresh_volume()

    print("\n[1/3] Applying schema …")
    try:
        apply_schema()
    except SystemExit as exc:
        # apply_schema exits when objects already exist. On a non-fresh run that
        # is expected — keep going to seed + ingest. (--fresh guarantees a clean DB.)
        if fresh:
            raise
        print("  schema already present — skipping (re-run with --fresh to rebuild)")

    print("\n[2/3] Seeding demo data …")
    for table, n in seed_all().items():
        print(f"  seeded {n:>2} {table}")

    print("\n[3/3] Ingesting seed KB (Gemini embeddings) …")
    chunks = ingest_seed_kb()
    print(f"  ingested {len(chunks)} KB chunks")

    print("\n✅ Database ready. Start the servers:")
    print("   uvicorn backend.main:app --reload")
    print("   (in frontend/) npm run dev")

    # Close the shared pool now, while the interpreter is still alive, so its
    # destructor doesn't fire too late during shutdown (Python 3.14).
    close_pool()


if __name__ == "__main__":
    try:
        main(fresh="--fresh" in sys.argv)
    except KeyboardInterrupt:
        sys.exit(130)
