#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# Sunwell Development Server
# Launches both the Python API server and Vite frontend simultaneously
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}☀️  Starting Sunwell Development Environment${NC}"
echo ""

# Trap to clean up background processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    # Kill all background jobs
    jobs -p | xargs -r kill 2>/dev/null || true
    wait 2>/dev/null
    echo -e "${GREEN}✨ Clean exit${NC}"
}
trap cleanup EXIT INT TERM

# Get the script directory (handles being called from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if studio node_modules exists
if [ ! -d "studio/node_modules" ]; then
    echo -e "${YELLOW}📦 Installing Studio dependencies...${NC}"
    cd studio && npm install && cd ..
fi

echo -e "${CYAN}🐍 Starting Python API server (port 8080)...${NC}"
sunwell serve --dev &
API_PID=$!

# Wait a moment for the API to start
sleep 1

echo -e "${CYAN}⚡ Starting Vite dev server (port 5173)...${NC}"
cd studio && npm run dev &
VITE_PID=$!

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ☀️  Sunwell Development Environment Running${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Frontend:${NC}  http://localhost:5173"
echo -e "  ${CYAN}API:${NC}       http://localhost:8080"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo ""

# Wait for either process to exit
wait
