#!/usr/bin/env bash
# ------------------------------------------------------------------
# NaturalSentinel — Local development setup (macOS / Linux / WSL2)
#
# Usage:  ./scripts/setup.sh
#
# Installs prerequisites, creates a virtualenv, syncs dependencies,
# verifies tooling, configures git auth, and adds shell aliases.
# Safe to re-run — every step is idempotent.
# ------------------------------------------------------------------
set -euo pipefail

# ── Colours (disabled when piped) ─────────────────────────────────
if [ -t 1 ]; then
    BOLD="\033[1m"  GREEN="\033[32m"  YELLOW="\033[33m"
    RED="\033[31m"  RESET="\033[0m"
else
    BOLD=""  GREEN=""  YELLOW=""  RED=""  RESET=""
fi

info()  { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
fail()  { echo -e "${RED}[✗]${RESET} $*"; exit 1; }
step()  { echo -e "\n${BOLD}==> $*${RESET}"; }

# ── Detect platform ──────────────────────────────────────────────
detect_platform() {
    case "$(uname -s)" in
        Darwin) PLATFORM="macos" ;;
        Linux)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                PLATFORM="wsl2"
            else
                PLATFORM="linux"
            fi
            ;;
        *) fail "Unsupported platform: $(uname -s). Use scripts/setup.ps1 on Windows." ;;
    esac
    info "Detected platform: $PLATFORM"
}

# ── Locate project root (directory containing pyproject.toml) ────
find_project_root() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    if [ ! -f "$PROJECT_DIR/pyproject.toml" ]; then
        fail "Cannot find pyproject.toml — run this script from the repo root or scripts/ directory."
    fi
    cd "$PROJECT_DIR"
    info "Project root: $PROJECT_DIR"
}

# ── Check / install a command ────────────────────────────────────
need_cmd() {
    command -v "$1" &>/dev/null
}

install_uv() {
    if need_cmd uv; then
        info "uv $(uv --version 2>/dev/null | head -1) already installed"
        return
    fi
    warn "uv not found — installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the env so uv is available in this session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    need_cmd uv || fail "uv installation failed. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
    info "uv installed"
}

install_gh() {
    if need_cmd gh; then
        info "gh $(gh --version 2>/dev/null | head -1) already installed"
        return
    fi
    warn "GitHub CLI (gh) not found — installing..."
    case "$PLATFORM" in
        macos)
            if need_cmd brew; then
                brew install gh
            else
                warn "Homebrew not found. Install gh manually: https://cli.github.com"
                return
            fi
            ;;
        linux|wsl2)
            if need_cmd apt-get; then
                # Official GitHub CLI repo
                (type -p wget >/dev/null || sudo apt-get install wget -y) \
                    && sudo mkdir -p -m 755 /etc/apt/keyrings \
                    && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg \
                        | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
                    && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
                    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
                        | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
                    && sudo apt-get update \
                    && sudo apt-get install gh -y
            elif need_cmd dnf; then
                sudo dnf install -y gh
            else
                warn "Could not auto-install gh. Install manually: https://cli.github.com"
                return
            fi
            ;;
    esac
    need_cmd gh && info "gh installed" || warn "gh installation failed — install manually"
}

check_python() {
    # uv manages Python, but check that a compatible version is reachable
    local py_version
    py_version="$(uv python find 2>/dev/null || true)"
    if [ -n "$py_version" ]; then
        info "Python: $py_version"
    else
        warn "No Python >=3.11 found — uv will download one automatically during sync"
    fi
}

# ── PostgreSQL (via Docker) ──────────────────────────────────────
setup_postgres() {
    step "Setting up PostgreSQL with pgvector (Docker)"

    if ! need_cmd docker; then
        warn "Docker not found. PostgreSQL setup requires Docker."
        warn "Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
        warn "Skipping database setup — re-run this script after installing Docker."
        return
    fi

    # Verify Docker daemon is actually running
    if ! docker info &>/dev/null; then
        warn "Docker is installed but the daemon is not running."
        warn "Start Docker Desktop, then re-run this script."
        return
    fi

    local CONTAINER_NAME="naturalsentinel-postgres"
    local PG_IMAGE="pgvector/pgvector:0.8.2-pg17"
    local PG_PORT="${PGPORT:-5432}"
    local PG_USER="sentinel"
    local PG_PASS="sentinel"
    local PG_DB="naturalsentinel"

    # Check if container already exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            info "PostgreSQL container '${CONTAINER_NAME}' already running"
        else
            info "Starting existing PostgreSQL container..."
            if ! docker start "$CONTAINER_NAME" 2>/tmp/ns-docker-err.log; then
                local start_err
                start_err="$(cat /tmp/ns-docker-err.log 2>/dev/null)"
                rm -f /tmp/ns-docker-err.log
                if echo "$start_err" | grep -qi "port is already allocated\|address already in use\|bind"; then
                    warn "Port ${PG_PORT} is already in use by another process."
                    warn "Fix: stop the conflicting service, or recreate with a different port:"
                    warn "  docker rm ${CONTAINER_NAME}"
                    warn "  PGPORT=5433 ./scripts/setup.sh"
                else
                    warn "Failed to start container: $start_err"
                    warn "Try removing and recreating: docker rm ${CONTAINER_NAME} && re-run this script"
                fi
                warn "Skipping database setup."
                return
            fi
            rm -f /tmp/ns-docker-err.log
        fi
    else
        info "Creating PostgreSQL + pgvector container..."
        if ! docker run -d \
            --name "$CONTAINER_NAME" \
            -e POSTGRES_USER="$PG_USER" \
            -e POSTGRES_PASSWORD="$PG_PASS" \
            -e POSTGRES_DB="$PG_DB" \
            -p "${PG_PORT}:5432" \
            --restart unless-stopped \
            "$PG_IMAGE" 2>/tmp/ns-docker-err.log; then
            local err
            err="$(cat /tmp/ns-docker-err.log 2>/dev/null)"
            rm -f /tmp/ns-docker-err.log
            # Clean up the orphaned container so re-runs don't hit "name already in use"
            docker rm "$CONTAINER_NAME" &>/dev/null || true
            if echo "$err" | grep -qi "port is already allocated\|address already in use\|bind"; then
                warn "Port ${PG_PORT} is already in use."
                warn "Another PostgreSQL or service may be running on that port."
                warn "Fix: stop the conflicting service, or set PGPORT to a different port:"
                warn "  PGPORT=5433 ./scripts/setup.sh"
            else
                warn "Failed to create Docker container."
                warn "Error: $err"
            fi
            warn "Skipping database setup — resolve the issue above and re-run."
            return
        fi
        rm -f /tmp/ns-docker-err.log
    fi

    # Wait for postgres to be ready
    info "Waiting for PostgreSQL to accept connections..."
    for i in $(seq 1 30); do
        if docker exec "$CONTAINER_NAME" pg_isready -U "$PG_USER" -d "$PG_DB" -q 2>/dev/null; then
            break
        fi
        if [ "$i" -eq 30 ]; then
            warn "PostgreSQL not ready after 30s — continuing without DB setup"
            return
        fi
        sleep 1
    done

    # Enable pgvector extension
    docker exec "$CONTAINER_NAME" psql -U "$PG_USER" -d "$PG_DB" \
        -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null \
        && info "pgvector extension enabled" \
        || warn "Could not enable pgvector extension"

    info "PostgreSQL ready at localhost:${PG_PORT}"
    info "Connection: postgresql://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB}"

    # Write DATABASE_URL to .env (always update to match current port/credentials)
    local DB_URL="postgresql://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB}"
    export DATABASE_URL="$DB_URL"

    if [ ! -f "$PROJECT_DIR/.env" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env" 2>/dev/null || true
    fi
    if [ -f "$PROJECT_DIR/.env" ]; then
        if [ "$(uname -s)" = "Darwin" ]; then
            sed -i '' "s|^DATABASE_URL=.*|DATABASE_URL=${DB_URL}|" "$PROJECT_DIR/.env" 2>/dev/null || true
        else
            sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${DB_URL}|" "$PROJECT_DIR/.env" 2>/dev/null || true
        fi
        info "DATABASE_URL set in .env"
    fi
}

# ── Run Alembic migrations ───────────────────────────────────────
run_migrations() {
    local CONTAINER_NAME="naturalsentinel-postgres"

    # Ensure DATABASE_URL is in the environment (may have been set by setup_postgres,
    # or we read it from .env for idempotent re-runs)
    if [ -z "${DATABASE_URL:-}" ] && [ -f "$PROJECT_DIR/.env" ]; then
        DATABASE_URL="$(grep '^DATABASE_URL=' "$PROJECT_DIR/.env" | head -1 | cut -d= -f2-)"
        export DATABASE_URL
    fi

    if [ -z "${DATABASE_URL:-}" ]; then
        warn "DATABASE_URL not set — skipping migrations."
        warn "Run setup_postgres first, or set DATABASE_URL in .env"
        return
    fi

    # Only run if postgres is actually reachable
    if need_cmd docker && docker exec "$CONTAINER_NAME" pg_isready -q 2>/dev/null; then
        step "Running database migrations"
        if DATABASE_URL="$DATABASE_URL" uv run alembic upgrade head; then
            info "Migrations applied successfully"
        else
            warn "Alembic migrations failed."
            warn "DATABASE_URL=$DATABASE_URL"
            warn "Ensure PostgreSQL is running and the URL is correct."
            warn "Then run manually: DATABASE_URL=\$DATABASE_URL uv run alembic upgrade head"
        fi
    else
        warn "PostgreSQL not reachable — skipping migrations."
        warn "After starting the database, run: DATABASE_URL=$DATABASE_URL uv run alembic upgrade head"
    fi
}

# ── Create venv & sync deps ──────────────────────────────────────
setup_venv() {
    step "Creating virtualenv and syncing dependencies"
    uv sync --all-extras
    info "Dependencies synced"
}

# ── Verify tooling ──────────────────────────────────────────────
verify_tools() {
    step "Verifying dev tools"
    uv run ruff --version   && info "ruff OK"
    uv run mypy --version   && info "mypy OK"
    uv run pytest --version && info "pytest OK"
}

# ── Git auth ─────────────────────────────────────────────────────
setup_git_auth() {
    step "Configuring git authentication"
    # Check SSH first
    if ssh-add -l &>/dev/null && ssh -T git@github.com 2>&1 | grep -qi "successfully authenticated"; then
        info "SSH agent active and authenticated with GitHub"
        return
    fi

    # Fall back to gh CLI
    warn "SSH not available — configuring GitHub CLI as git credential helper"
    if need_cmd gh; then
        gh auth setup-git 2>/dev/null || true
        if gh auth status &>/dev/null; then
            info "gh CLI already authenticated"
        else
            echo ""
            echo "  ┌──────────────────────────────────────────────────────┐"
            echo "  │  Run the following to authenticate:                  │"
            echo "  │    gh auth login                                     │"
            echo "  └──────────────────────────────────────────────────────┘"
            echo ""
        fi
    else
        warn "Neither SSH agent nor gh CLI available — git push/pull may not work"
    fi
}

# ── Pre-commit hooks ─────────────────────────────────────────────
setup_precommit() {
    step "Installing pre-commit hooks"
    uv run pre-commit install
    info "Pre-commit hooks installed"
}

# ── Shell aliases ────────────────────────────────────────────────
setup_aliases() {
    step "Setting up shell aliases"

    # Determine the right rc file
    local rc_file
    case "${SHELL:-/bin/bash}" in
        */zsh)  rc_file="$HOME/.zshrc" ;;
        */fish) rc_file="$HOME/.config/fish/config.fish" ;;
        *)      rc_file="$HOME/.bashrc" ;;
    esac

    if grep -q "NaturalSentinel dev aliases" "$rc_file" 2>/dev/null; then
        info "Aliases already present in $rc_file"
        return
    fi

    local alias_block
    read -r -d '' alias_block <<'ALIASES' || true

# --- NaturalSentinel dev aliases ---

# ── Lint / Format / Type ──
alias lint="uv run ruff check src/ tests/"
alias lint:fix="uv run ruff check --fix src/ tests/"
alias fmt="uv run ruff format src/ tests/"
alias fmt:check="uv run ruff format --check src/ tests/"
alias typecheck="uv run mypy"
alias check="uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy"

# ── Test ──
alias test="uv run pytest"
alias test:cov="uv run pytest --cov"
alias test:watch="uv run pytest -x --tb=short"
alias test:v="uv run pytest -v"
alias test:last="uv run pytest --lf"

# ── Build / Deps ──
alias build="uv build"
alias deps="uv sync --all-extras"
alias deps:add="uv add"
alias deps:rm="uv remove"
alias deps:tree="uv tree"
alias deps:lock="uv lock"
alias deps:up="uv lock --upgrade && uv sync --all-extras"

# ── Python ──
alias py="uv run python"
alias ipy="uv run python -i"
alias pip="uv pip"

# ── Git shortcuts ──
alias gs="git status"
alias gd="git diff"
alias gds="git diff --staged"
alias gl="git log --oneline -20"
alias gla="git log --oneline --all --graph -20"
alias gb="git branch -v"
alias gco="git checkout"
alias gcb="git checkout -b"
alias ga="git add"
alias gap="git add -p"
alias gc="git commit"
alias gcm="git commit -m"
alias gca="git commit --amend"
alias gp="git push"
alias gpu="git push -u origin HEAD"
alias gpf="git push --force-with-lease"
alias gpl="git pull --rebase"
alias gf="git fetch --all --prune"
alias gst="git stash"
alias gstp="git stash pop"
alias grb="git rebase"
alias grbi="git rebase -i"
alias gcp="git cherry-pick"
alias grs="git reset"
alias gbl="git blame"
alias gclean="git branch --merged main | grep -v main | xargs -r git branch -d"

# ── GitHub CLI ──
alias prs="gh pr list"
alias pr="gh pr view --web"
alias prc="gh pr create --fill"
alias prco="gh pr checkout"
alias issues="gh issue list"
alias repo="gh repo view --web"

# --- end NaturalSentinel dev aliases ---
ALIASES

    echo "$alias_block" >> "$rc_file"
    info "Aliases added to $rc_file"
    warn "Run 'source $rc_file' or open a new terminal to activate"
}

# ── Print summary ────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${BOLD}══════════════════════════════════════════════════════${RESET}"
    echo -e "${GREEN}  NaturalSentinel dev environment ready!${RESET}"
    echo -e "${BOLD}══════════════════════════════════════════════════════${RESET}"
    echo ""
    echo "  Activate the virtualenv (if not using uv run):"
    echo "    source .venv/bin/activate"
    echo ""
    echo "  Pre-commit hook active — runs on every commit:"
    echo "    ruff format --check, ruff check, pytest"
    echo ""
    echo "  Database:"
    echo "    PostgreSQL + pgvector via Docker (naturalsentinel-postgres)"
    echo "    Connection:   \$DATABASE_URL (see .env)"
    echo "    Migrations:   uv run alembic upgrade head"
    echo ""
    echo "  Quick start:"
    echo "    test          — run tests"
    echo "    check         — lint + format + typecheck"
    echo "    py            — python REPL"
    echo "    deps          — sync dependencies"
    echo ""
    echo "  Run 'alias | grep -E \"^(g|test|lint|fmt|dep|pr|py)\"' to see all aliases."
    echo ""
}

# ── Main ─────────────────────────────────────────────────────────
main() {
    echo -e "${BOLD}NaturalSentinel — Local Development Setup${RESET}"
    echo ""

    detect_platform
    find_project_root

    step "Checking prerequisites"
    install_uv
    check_python
    install_gh

    setup_postgres
    setup_venv
    run_migrations
    verify_tools
    setup_precommit
    setup_git_auth
    setup_aliases
    print_summary
}

main "$@"
