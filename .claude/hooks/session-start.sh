#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if ! command -v rea >/dev/null 2>&1; then
  npm install --global rea-agents
fi

rea setup --client claude_code --yes --json
