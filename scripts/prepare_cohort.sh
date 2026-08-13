#!/usr/bin/env bash
# Ingest all 5ULTRA cohort TSVs (splice + nosplice) into SQLite + per-sample tracks.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 ingest/ingest_cohort.py "$@"
