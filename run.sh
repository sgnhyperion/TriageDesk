#!/usr/bin/env bash
# One-shot local backend bring-up:
#   venv -> deps -> .env -> Docker DB -> fresh schema+seed+KB -> live API
#
# Usage (from repo root):
#   ./run.sh              # full setup + start the API
#   ./run.sh --keep-db    # don't wipe the DB (skip the --fresh rebuild)
#
# Idempotent: re-running is safe. Frontend is separate: `cd frontend && npm run dev`.
set -euo pipefail
cd "$(dirname "$0")"

FRESH="--fresh"
[[ "${1:-}" == "--keep-db" ]] && FRESH=""

echo "==> [1/5] Python venv"
[[ -d .venv ]] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> [2/5] Dependencies"
pip install -q -r backend/requirements.txt

echo "==> [3/5] Env file"
[[ -f backend/.env ]] || cp backend/.env.example backend/.env

echo "==> [4/5] Database (Docker) + setup"
if ! docker info >/dev/null 2>&1; then
  echo "    ✗ Docker Desktop is not running — start it and re-run ./run.sh" >&2
  exit 1
fi
docker compose up -d
python -m backend.scripts.setup_db $FRESH

echo "==> [5/5] API  ->  http://localhost:8000/docs   (Ctrl-C to stop)"
echo "    Frontend (separate terminal):  cd frontend && npm install && npm run dev"
exec uvicorn backend.main:app --reload
