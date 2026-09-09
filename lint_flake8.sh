#!/usr/bin/env bash
set -euo pipefail
if command -v flake8 >/dev/null 2>&1; then
  flake8 trpc_service
else
  echo "flake8 is not installed; install it for the CI lint gate"
fi
