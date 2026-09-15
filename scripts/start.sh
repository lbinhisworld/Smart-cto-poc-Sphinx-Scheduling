#!/usr/bin/env bash
# 一体化 POC：启动 API（前端请另开终端 cd web && npm run dev）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "→ API  http://127.0.0.1:8000/api/health"
echo "→ Web  http://127.0.0.1:5180 （cd web && npm run dev）"
exec .venv/bin/python -m uvicorn api.app_factory:app --host 127.0.0.1 --port 8000 --reload
