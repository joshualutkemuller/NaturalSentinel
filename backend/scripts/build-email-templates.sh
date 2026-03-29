#!/usr/bin/env bash
# Build MJML email templates into HTML.
# Requires: npx (Node.js)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/../app/email-templates"

mkdir -p "$TEMPLATES_DIR/build"
npx mjml@4 "$TEMPLATES_DIR/src/"*.mjml -o "$TEMPLATES_DIR/build/"

echo "Built email templates → $TEMPLATES_DIR/build/"
