# ------------------------------------------------------------------
# NaturalSentinel — Local development setup (Windows / PowerShell)
#
# Usage:  .\scripts\setup.ps1
#
# Installs prerequisites, creates a virtualenv, syncs dependencies,
# verifies tooling, configures git auth, and adds shell aliases.
# Safe to re-run — every step is idempotent.
# ------------------------------------------------------------------
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

# ── Helpers ──────────────────────────────────────────────────────
function Write-Step   { param([string]$msg) Write-Host "`n==> $msg" -ForegroundColor White }
function Write-Ok     { param([string]$msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn   { param([string]$msg) Write-Host "[!]  $msg" -ForegroundColor Yellow }
function Write-Fail   { param([string]$msg) Write-Host "[X]  $msg" -ForegroundColor Red; exit 1 }

function Test-Command { param([string]$cmd) return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# ── Locate project root ─────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

if (-not (Test-Path (Join-Path $ProjectDir "pyproject.toml"))) {
    Write-Fail "Cannot find pyproject.toml — run this script from the repo root or scripts\ directory."
}
Set-Location $ProjectDir
Write-Ok "Project root: $ProjectDir"

# ── Install uv ──────────────────────────────────────────────────
Write-Step "Checking prerequisites"

if (Test-Command "uv") {
    $uvVer = & uv --version 2>&1 | Select-Object -First 1
    Write-Ok "uv $uvVer already installed"
} else {
    Write-Warn "uv not found — installing..."
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
        if (-not (Test-Command "uv")) { throw "uv not on PATH" }
        Write-Ok "uv installed"
    } catch {
        Write-Fail "uv installation failed. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
    }
}

# ── Check Python ────────────────────────────────────────────────
$pyPath = & uv python find 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok "Python: $pyPath"
} else {
    Write-Warn "No Python >=3.11 found — uv will download one automatically during sync"
}

# ── Install GitHub CLI ──────────────────────────────────────────
if (Test-Command "gh") {
    $ghVer = & gh --version 2>&1 | Select-Object -First 1
    Write-Ok "gh $ghVer already installed"
} else {
    Write-Warn "GitHub CLI (gh) not found — installing..."
    $installed = $false

    # Try winget first
    if (Test-Command "winget") {
        try {
            & winget install --id GitHub.cli --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
            $installed = Test-Command "gh"
        } catch {}
    }

    # Try scoop
    if (-not $installed -and (Test-Command "scoop")) {
        try {
            & scoop install gh 2>&1 | Out-Null
            $installed = Test-Command "gh"
        } catch {}
    }

    # Try choco
    if (-not $installed -and (Test-Command "choco")) {
        try {
            & choco install gh -y 2>&1 | Out-Null
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + $env:Path
            $installed = Test-Command "gh"
        } catch {}
    }

    if ($installed) {
        Write-Ok "gh installed"
    } else {
        Write-Warn "Could not auto-install gh. Install manually: https://cli.github.com"
    }
}

# ── Create venv & sync deps ────────────────────────────────────
Write-Step "Creating virtualenv and syncing dependencies"
& uv sync --all-extras
if ($LASTEXITCODE -ne 0) { Write-Fail "uv sync failed" }
Write-Ok "Dependencies synced"

# ── Verify tooling ──────────────────────────────────────────────
Write-Step "Verifying dev tools"
& uv run ruff --version  2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { Write-Ok "ruff OK" }   else { Write-Warn "ruff not working" }
& uv run mypy --version  2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { Write-Ok "mypy OK" }   else { Write-Warn "mypy not working" }
& uv run pytest --version 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { Write-Ok "pytest OK" } else { Write-Warn "pytest not working" }

# ── Git auth ────────────────────────────────────────────────────
Write-Step "Configuring git authentication"

$sshOk = $false
try {
    $sshResult = & ssh -T git@github.com 2>&1
    if ($sshResult -match "successfully authenticated") { $sshOk = $true }
} catch {}

if ($sshOk) {
    Write-Ok "SSH authenticated with GitHub"
} elseif (Test-Command "gh") {
    Write-Warn "SSH not available — configuring gh CLI as git credential helper"
    & gh auth setup-git 2>&1 | Out-Null

    $ghAuthed = $false
    try { & gh auth status 2>&1 | Out-Null; $ghAuthed = ($LASTEXITCODE -eq 0) } catch {}

    if ($ghAuthed) {
        Write-Ok "gh CLI already authenticated"
    } else {
        Write-Host ""
        Write-Host "  +------------------------------------------------------+"
        Write-Host "  |  Run the following to authenticate:                   |"
        Write-Host "  |    gh auth login                                      |"
        Write-Host "  +------------------------------------------------------+"
        Write-Host ""
    }
} else {
    Write-Warn "Neither SSH nor gh CLI available — git push/pull may not work"
}

# ── PowerShell aliases (profile) ────────────────────────────────
Write-Step "Setting up PowerShell aliases & functions"

$profileDir = Split-Path -Parent $PROFILE
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir -Force | Out-Null }
if (-not (Test-Path $PROFILE))    { New-Item -ItemType File -Path $PROFILE -Force | Out-Null }

$marker = "NaturalSentinel dev aliases"
$profileContent = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue

if ($profileContent -and $profileContent.Contains($marker)) {
    Write-Ok "Aliases already present in $PROFILE"
} else {
    # PowerShell uses functions for aliases with arguments
    $aliasBlock = @'

# --- NaturalSentinel dev aliases ---

# ── Lint / Format / Type ──
function lint       { uv run ruff check src/ tests/ }
function lint-fix   { uv run ruff check --fix src/ tests/ }
function fmt-code   { uv run ruff format src/ tests/ }
function fmt-check  { uv run ruff format --check src/ tests/ }
function typecheck  { uv run mypy }
function check-all  { uv run ruff check src/ tests/; uv run ruff format --check src/ tests/; uv run mypy }

# ── Test ──
function test-run   { uv run pytest @args }
function test-cov   { uv run pytest --cov @args }
function test-watch { uv run pytest -x --tb=short @args }
function test-v     { uv run pytest -v @args }
function test-last  { uv run pytest --lf @args }

# ── Build / Deps ──
function build-pkg  { uv build }
function deps       { uv sync --all-extras }
function deps-add   { uv add @args }
function deps-rm    { uv remove @args }
function deps-tree  { uv tree }
function deps-lock  { uv lock }
function deps-up    { uv lock --upgrade; uv sync --all-extras }

# ── Python ──
function py         { uv run python @args }
function ipy        { uv run python -i @args }

# ── Git shortcuts ──
function gs         { git status }
function gd         { git diff @args }
function gds        { git diff --staged @args }
function gl         { git log --oneline -20 }
function gla        { git log --oneline --all --graph -20 }
function gb         { git branch -v }
function gco        { git checkout @args }
function gcb        { git checkout -b @args }
function ga         { git add @args }
function gap        { git add -p @args }
function gc-commit  { git commit @args }
function gcm        { param([string]$m) git commit -m $m }
function gca        { git commit --amend @args }
function gp         { git push @args }
function gpu        { git push -u origin HEAD }
function gpf        { git push --force-with-lease @args }
function gpl        { git pull --rebase @args }
function gf         { git fetch --all --prune }
function gst-stash  { git stash @args }
function gstp       { git stash pop }
function grb        { git rebase @args }
function gcp-pick   { git cherry-pick @args }
function gbl        { git blame @args }

# ── GitHub CLI ──
function prs        { gh pr list @args }
function pr-view    { gh pr view --web }
function prc        { gh pr create --fill @args }
function prco       { gh pr checkout @args }
function issues     { gh issue list @args }
function repo-web   { gh repo view --web }

# --- end NaturalSentinel dev aliases ---
'@

    Add-Content -Path $PROFILE -Value $aliasBlock
    Write-Ok "Aliases added to $PROFILE"
    Write-Warn "Run '. `$PROFILE' or open a new terminal to activate"
}

# ── Summary ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "======================================================" -ForegroundColor White
Write-Host "  NaturalSentinel dev environment ready!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor White
Write-Host ""
Write-Host "  Activate the virtualenv (if not using uv run):"
Write-Host "    .venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "  Quick start:"
Write-Host "    test-run      - run tests"
Write-Host "    check-all     - lint + format + typecheck"
Write-Host "    py            - python REPL"
Write-Host "    deps          - sync dependencies"
Write-Host ""
