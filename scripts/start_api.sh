#!/usr/bin/env bash
# Start API (and optionally rebuild tracks from example.tsv).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "--reingest" ]]; then
  python3 ingest/run_ingest.py example.tsv
fi

export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT/backend"
PORT="${PORT:-8001}"
exec python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
