#!/bin/bash
# SessionStart hook: prepare the Python environment so tests and linters work
# in Claude Code on the web. Idempotent and non-interactive.
set -euo pipefail

# Only run in the remote (web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

VENV=".venv"

# A clean venv avoids the system Python's Debian-managed package conflicts.
if [ ! -x "$VENV/bin/python" ]; then
  python -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade --quiet pip
# Project deps (includes pytest) + ruff for linting (configured in pyproject).
"$VENV/bin/pip" install --quiet -r requirements.txt
"$VENV/bin/pip" install --quiet ruff

# Make the venv tools (python, pytest, ruff) resolve for the rest of the session.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export PATH=\"$PWD/$VENV/bin:\$PATH\""
    echo "export VIRTUAL_ENV=\"$PWD/$VENV\""
  } >> "$CLAUDE_ENV_FILE"
fi

echo "Command Hub environment ready (venv + deps installed)."
