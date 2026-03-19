#!/usr/bin/env bash
# ------------------------------------------------------------------
# NaturalSentinel devcontainer post-create setup
# Runs once when the container is first created.
# ------------------------------------------------------------------
set -euo pipefail

PROJECT_DIR="/workspaces/NaturalSentinel"
cd "$PROJECT_DIR"

echo "==> Creating venv and syncing dependencies with uv..."
uv sync --all-extras

echo "==> Verifying tool availability..."
uv run ruff  --version
uv run mypy  --version
uv run pytest --version

# ------------------------------------------------------------------
# Shell aliases — written to ~/.bashrc so they persist in every
# terminal the developer opens inside the container.
# ------------------------------------------------------------------
ALIAS_BLOCK='
# --- NaturalSentinel dev aliases ---
alias lint="uv run ruff check src/ tests/"
alias lint:fix="uv run ruff check --fix src/ tests/"
alias fmt="uv run ruff format src/ tests/"
alias fmt:check="uv run ruff format --check src/ tests/"
alias typecheck="uv run mypy"
alias test="uv run pytest"
alias test:cov="uv run pytest --cov"
alias test:watch="uv run pytest -x --tb=short"
alias build="uv build"
'

# Append only if not already present
if ! grep -q "NaturalSentinel dev aliases" ~/.bashrc 2>/dev/null; then
    echo "$ALIAS_BLOCK" >> ~/.bashrc
fi

echo "==> Dev environment ready. Available aliases:"
echo "    lint        - ruff check src/ tests/"
echo "    lint:fix    - ruff check --fix src/ tests/"
echo "    fmt         - ruff format src/ tests/"
echo "    fmt:check   - ruff format --check src/ tests/"
echo "    typecheck   - mypy"
echo "    test        - pytest"
echo "    test:cov    - pytest --cov"
echo "    build       - uv build"
