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

    setup_venv
    verify_tools
    setup_git_auth
    setup_aliases
    print_summary
}

main "$@"
