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
# Pre-commit hooks
# ------------------------------------------------------------------
echo "==> Installing pre-commit hooks..."
uv run pre-commit install

# ------------------------------------------------------------------
# Shell aliases — written to ~/.bashrc so they persist in every
# terminal the developer opens inside the container.
# ------------------------------------------------------------------
ALIAS_BLOCK='
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
alias pypath="uv run python -c \"import sys; print(\"\n\".join(sys.path))\""
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
'

# Append only if not already present
if ! grep -q "NaturalSentinel dev aliases" ~/.bashrc 2>/dev/null; then
    echo "$ALIAS_BLOCK" >> ~/.bashrc
fi

# ------------------------------------------------------------------
# Git auth: prefer SSH agent forwarding, fall back to gh CLI
# ------------------------------------------------------------------
echo "==> Configuring git authentication..."
if ssh-add -l &>/dev/null && ssh -T git@github.com 2>&1 | grep -qi "successfully authenticated"; then
    echo "    SSH agent forwarded — using SSH for git operations."
else
    echo "    SSH agent not available or not authenticated with GitHub."
    echo "    Falling back to GitHub CLI authentication..."
    if gh auth status &>/dev/null; then
        echo "    gh CLI already authenticated."
    else
        echo ""
        echo "    ┌──────────────────────────────────────────────────────┐"
        echo "    │  GitHub CLI login required for git push/pull.       │"
        echo "    │  Run: gh auth login                                 │"
        echo "    │  Then: gh auth setup-git                            │"
        echo "    └──────────────────────────────────────────────────────┘"
        echo ""
    fi
    # Configure git to use gh as credential helper (idempotent, works
    # even before login — git will prompt via gh when credentials are
    # needed at push/pull time)
    gh auth setup-git 2>/dev/null || true
fi

echo "==> Dev environment ready!"
echo ""
echo "  Lint / Format / Type:"
echo "    lint        ruff check          lint:fix    ruff check --fix"
echo "    fmt         ruff format         fmt:check   ruff format --check"
echo "    typecheck   mypy                check       lint + fmt:check + mypy"
echo ""
echo "  Test:"
echo "    test        pytest              test:cov    pytest --cov"
echo "    test:v      pytest -v           test:last   pytest --lf (rerun failures)"
echo "    test:watch  pytest -x --tb=short"
echo ""
echo "  Deps (uv):"
echo "    deps        sync all            deps:add    add a package"
echo "    deps:rm     remove a package    deps:tree   show dep tree"
echo "    deps:up     upgrade & sync      deps:lock   regenerate lockfile"
echo ""
echo "  Python:"
echo "    py          python              ipy         interactive python"
echo "    pip         uv pip              build       uv build"
echo ""
echo "  Git:"
echo "    gs  status    gd  diff       gl  log        gb  branches"
echo "    ga  add       gap add -p     gc  commit     gcm commit -m"
echo "    gp  push      gpu push -u    gpf push --fl  gpl pull --rebase"
echo "    gco checkout  gcb new branch gf  fetch      gst stash"
echo ""
echo "  GitHub CLI:"
echo "    prs         list PRs            pr          open PR in browser"
echo "    prc         create PR           prco        checkout a PR"
echo "    issues      list issues         repo        open repo in browser"
