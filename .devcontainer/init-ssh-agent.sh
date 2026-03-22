#!/usr/bin/env bash
# ------------------------------------------------------------------
# Runs on the HOST before the devcontainer starts.
# Ensures the SSH agent is running so VS Code can forward it into
# the container. Gives platform-specific guidance on failure.
# ------------------------------------------------------------------

check_ssh_agent() {
    # If SSH_AUTH_SOCK is set and the socket exists, agent is running
    if [ -n "$SSH_AUTH_SOCK" ] && [ -e "$SSH_AUTH_SOCK" ]; then
        return 0
    fi
    return 1
}

if check_ssh_agent; then
    echo "[devcontainer] SSH agent detected — keys will be forwarded into the container."
    ssh-add -l 2>/dev/null || echo "[devcontainer] WARNING: SSH agent is running but has no keys. Run: ssh-add"
    exit 0
fi

# Detect platform and give specific guidance
case "$(uname -s)" in
    Darwin)
        echo "[devcontainer] SSH agent not detected on macOS."
        echo "  Attempting to start it..."
        eval "$(ssh-agent -s)"
        ssh-add --apple-use-keychain 2>/dev/null || ssh-add
        echo "  TIP: Add this to ~/.zshrc to start automatically:"
        echo '    eval "$(ssh-agent -s)" && ssh-add --apple-use-keychain 2>/dev/null'
        ;;
    Linux)
        if grep -qi microsoft /proc/version 2>/dev/null; then
            # --- WSL2 ---
            echo "[devcontainer] SSH agent not detected in WSL2."
            echo ""
            echo "  Option 1 — Use SSH keys inside WSL2 (simplest):"
            echo "    1. Generate or copy keys into ~/.ssh/ inside WSL2"
            echo "    2. Add to ~/.bashrc:"
            echo '       if [ -z "$SSH_AUTH_SOCK" ]; then eval "$(ssh-agent -s)" && ssh-add; fi'
            echo ""
            echo "  Option 2 — Forward the Windows OpenSSH agent into WSL2:"
            echo "    1. Enable Windows OpenSSH Agent (PowerShell as Admin):"
            echo "       Set-Service ssh-agent -StartupType Automatic"
            echo "       Start-Service ssh-agent"
            echo "       ssh-add"
            echo "    2. Install socat in WSL2: sudo apt install socat"
            echo "    3. Install npiperelay:"
            echo "       https://github.com/jstarks/npiperelay/releases"
            echo "       Place npiperelay.exe somewhere in your Windows PATH"
            echo "    4. Add to ~/.bashrc in WSL2:"
            echo '       export SSH_AUTH_SOCK="$HOME/.ssh/agent.sock"'
            echo '       if ! ss -a | grep -q "$SSH_AUTH_SOCK"; then'
            echo '         rm -f "$SSH_AUTH_SOCK"'
            echo '         (setsid socat UNIX-LISTEN:"$SSH_AUTH_SOCK",fork \'
            echo '           EXEC:"npiperelay.exe -ei -s //./pipe/openssh-ssh-agent" &>/dev/null &)'
            echo '       fi'
            echo ""
            # Still try to start a local agent as a fallback
            echo "  Attempting to start a local SSH agent as fallback..."
            eval "$(ssh-agent -s)"
            ssh-add 2>/dev/null || true
        else
            # --- Native Linux ---
            echo "[devcontainer] SSH agent not detected on Linux."
            echo "  Attempting to start it..."
            eval "$(ssh-agent -s)"
            ssh-add
            echo "  TIP: Add this to ~/.bashrc to start automatically:"
            echo '    if [ -z "$SSH_AUTH_SOCK" ]; then eval "$(ssh-agent -s)" && ssh-add; fi'
        fi
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo "[devcontainer] SSH agent not detected on Windows (Git Bash)."
        echo ""
        echo "  Option 1 — Enable the Windows OpenSSH Agent (recommended):"
        echo "    1. Open PowerShell as Administrator"
        echo "    2. Run: Set-Service ssh-agent -StartupType Automatic"
        echo "    3. Run: Start-Service ssh-agent"
        echo "    4. Run: ssh-add"
        echo ""
        echo "  Option 2 — Start from Git Bash:"
        echo '    eval "$(ssh-agent -s)" && ssh-add'
        echo ""
        echo "  After enabling, restart VS Code and reopen in container."
        # Don't fail — let the container build; SSH just won't work
        ;;
    *)
        echo "[devcontainer] WARNING: Could not detect platform for SSH agent setup."
        echo "  Ensure ssh-agent is running and SSH_AUTH_SOCK is set."
        ;;
esac

# Exit 0 regardless — missing SSH shouldn't block the container build
exit 0
