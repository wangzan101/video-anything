#!/usr/bin/env bash
# Stable compatibility entry point for the validated Python download pipeline.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VA_HOME="${VA_HOME:-$HOME/.video-anything}"
export PATH="$VA_HOME/bin:$PATH"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

exec python3 "$SCRIPT_DIR/fetch.py" "$@"
