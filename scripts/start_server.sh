#!/usr/bin/env bash
# ------------------------------------------------------------------
# NaturalSentinel — Start the FastAPI development server
#
# Works in both the devcontainer and on a local host machine.
#
# Usage:
#   ./scripts/start_server.sh              # defaults: 0.0.0.0:8000, reload on
#   ./scripts/start_server.sh --port 3000
#   ./scripts/start_server.sh --no-reload
#   API_PORT=9000 ./scripts/start_server.sh
# ------------------------------------------------------------------
set -euo pipefail

# ── Locate project root ─────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ── Load .env first so CLI flags and explicit env vars win ───────
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

# ── Defaults (env → fallback, then CLI flags override below) ─────
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
RELOAD="--reload"
LOG_LEVEL="${LOG_LEVEL:-info}"

# ── Parse CLI flags ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)       API_HOST="$2"; shift 2 ;;
        --port)       API_PORT="$2"; shift 2 ;;
        --no-reload)  RELOAD=""; shift ;;
        --log-level)  LOG_LEVEL="$2"; shift 2 ;;
        *)            echo "Unknown flag: $1"; exit 1 ;;
    esac
done

# ── Detect environment ──────────────────────────────────────────
if [ -f /.dockerenv ] || [ -f /run/.containerenv ]; then
    ENV_LABEL="devcontainer"
else
    ENV_LABEL="local"
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║  NaturalSentinel API Server                     ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Environment:  ${ENV_LABEL}"
echo "║  Address:      http://${API_HOST}:${API_PORT}"
echo "║  Docs:         http://${API_HOST}:${API_PORT}/docs"
echo "║  Reload:       ${RELOAD:-off}"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Start uvicorn ───────────────────────────────────────────────
exec uv run uvicorn \
    naturalsentinel.api.app:app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    --log-level "$LOG_LEVEL" \
    $RELOAD
