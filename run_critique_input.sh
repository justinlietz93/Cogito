#!/usr/bin/env bash
set -Eeuo pipefail

# Run Cogito critique on the INPUT directory with scientific + peer review + LaTeX enabled.
# Usage:
#   bash run_critique_input.sh [additional args...]
# Examples:
#   bash run_critique_input.sh --output-dir critiques
#   ./run_critique_input.sh --no-PR     # after chmod +x
#
# Notes:
# - This script must be run from the repository root (where run_critique.py lives).
# - If a local virtual environment (.venv or venv) is present, it will be auto-activated.
# - Any extra CLI flags you pass will be forwarded to run_critique.py.

# Resolve to repository root (directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Auto-activate virtualenv if present
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1090
    . ".venv/bin/activate"
  elif [[ -f "venv/bin/activate" ]]; then
    # shellcheck disable=SC1090
    . "venv/bin/activate"
  fi
fi

# Choose python interpreter
PYTHON_BIN="python"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  fi
fi

# Ensure INPUT directory exists
if [[ ! -d "INPUT" ]]; then
  echo "Error: INPUT directory not found at $(pwd)/INPUT" >&2
  exit 1
fi

# Execute critique with directory ingestion, forwarding any extra args
exec "$PYTHON_BIN" run_critique.py INPUT --scientific --PR --latex "$@"