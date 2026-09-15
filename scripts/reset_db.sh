#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
rm -f data/scheduling.db
export PYTHONPATH="$ROOT"
.venv/bin/python scripts/import_seed.py
echo "已重建 data/scheduling.db"
