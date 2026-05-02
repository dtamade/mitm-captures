#!/usr/bin/env bash
# ai.sh - shortest entry for AI-ready bundle output

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/analyzeLatest.sh" --stdout "$@"

