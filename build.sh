#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  uv venv --allow-existing .venv
  uv pip install --python .venv/bin/python "fastapi>=0.110" "uvicorn>=0.29"
else
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install "fastapi>=0.110" "uvicorn>=0.29"
fi
echo "environment ready; run: .venv/bin/python -m trpc_service._cli demo"
