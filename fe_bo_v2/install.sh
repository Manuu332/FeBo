#!/usr/bin/env bash
# FeBo Merged v2 — Install Script
set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${CYAN}[FeBo]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }

echo -e "${CYAN}"
cat << 'BANNER'
╔══════════════════════════════════════════════════╗
║  FeBo — Developmental Cognitive Architecture     ║
║  Merged v2 Install                               ║
╚══════════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

PYTHON=${PYTHON:-python3}
$PYTHON -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'" || {
  echo "Python 3.10+ required"; exit 1
}
success "Python version OK"

# Create directories
mkdir -p memory logs data
success "Directories created"

# Copy .env if missing
[ -f .env ] || { cp .env.example .env 2>/dev/null || true; info ".env created (edit to add API keys)"; }

info "Installing core dependencies..."
pip install torch numpy sqlalchemy cryptography python-dotenv rich \
    requests beautifulsoup4 psutil colorama tqdm pyyaml \
    --quiet --break-system-packages 2>/dev/null || \
pip install torch numpy sqlalchemy cryptography python-dotenv rich \
    requests beautifulsoup4 psutil colorama tqdm pyyaml --quiet

success "Core dependencies installed"

info "Installing optional dependencies..."
pip install trafilatura aiohttp sentence-transformers chromadb \
    --quiet --break-system-packages 2>/dev/null || \
warn "Some optional dependencies unavailable — FeBo will use fallbacks"

pip install pytest --quiet --break-system-packages 2>/dev/null || true

info "Running smoke test..."
$PYTHON -c "
import sys; sys.path.insert(0, '.')
from config.settings import FEBO_NAME
from core.logging_config import get_logger
from core.runtime_state import runtime
from core.scheduler import scheduler
from brain.emotion import load_state
from brain.soul import process_input
print(f'  FeBo={FEBO_NAME}')
print(f'  Runtime: {runtime}')
print(f'  Emotion: {load_state()[\"dominant_mood\"]}')
resp = process_input('Hello FeBo')
print(f'  Soul loop: OK -> {resp[:40]}')
" && success "Smoke test passed" || { echo "Smoke test failed — check output above"; exit 1; }

echo ""
echo -e "${GREEN}═══ FeBo Merged v2 ready ═══${NC}"
echo ""
echo "  python main.py           → full boot + CLI"
echo "  python -m pytest tests/  → run test suite"
echo "  cat ARCHITECTURE.md      → architecture decisions"
echo "  tail -f logs/febo.log    → live log stream"
echo ""
