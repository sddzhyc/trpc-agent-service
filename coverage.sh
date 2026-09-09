#!/usr/bin/env bash
set -euo pipefail
if command -v pytest >/dev/null 2>&1; then
  pytest --cov=trpc_service --cov-report=term-missing
else
  echo "pytest is not installed; install pytest pytest-cov for the Week 4 gate"
fi
