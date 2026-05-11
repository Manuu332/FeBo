#!/usr/bin/env bash
# start.sh — Launch FeBo Terminal v0
# Run from the feebo/ project root.

set -e

echo ""
echo "  ███████ ███████ ██████   ██████  "
echo "  ██      ██      ██   ██ ██    ██ "
echo "  █████   █████   ██████  ██    ██ "
echo "  ██      ██      ██   ██ ██    ██ "
echo "  ██      ███████ ██████   ██████  "
echo ""
echo "  FeBo Terminal v0 — starting up"
echo ""

# Load .env if present
if [ -f .env ]; then
  echo "  ✓ Loading .env"
  export $(grep -v '^#' .env | xargs)
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "  ⚠  WARNING: ANTHROPIC_API_KEY not set."
  echo "     FeBo will run in stub mode (no LLM responses)."
  echo "     Set it in .env or Codespaces secrets."
  echo ""
fi

# Create required directories
mkdir -p data logs

# Run
PORT=${PORT:-8000}
echo "  → Listening on http://0.0.0.0:$PORT"
echo ""

cd "$(dirname "$0")"
uvicorn interface.app:app --host 0.0.0.0 --port "$PORT" --reload
