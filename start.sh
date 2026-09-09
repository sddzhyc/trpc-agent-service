#!/usr/bin/env bash
set -euo pipefail
exec python -m trpc_service._cli serve
