#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

pip install -q fastapi uvicorn python-dotenv aiofiles jinja2 2>/dev/null || true

mkdir -p data logs

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   FeBo Terminal v3 — Autonomous          ║"
echo "  ║   No external model. She speaks herself. ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

uvicorn interface.app:app --host 0.0.0.0 --port 8000 --reload
