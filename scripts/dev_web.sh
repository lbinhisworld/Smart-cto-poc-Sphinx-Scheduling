#!/usr/bin/env bash
# 本地演示：先起后端 8000，再起前端 5180（需两个终端，或本脚本只起后端）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "→ API  http://127.0.0.1:8000/api/health"
echo "→ 看板 http://127.0.0.1:5180 （另开终端: cd web && npm run dev）"
exec .venv/bin/python -m uvicorn api.app_factory:app --host 127.0.0.1 --port 8000 --reload
