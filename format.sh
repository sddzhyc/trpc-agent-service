#!/usr/bin/env bash
set -euo pipefail
if command -v ruff >/dev/null 2>&1; then
  ruff format trpc_service
else
  echo "ruff is not installed; formatting is a Week 4 CI step"
fi
