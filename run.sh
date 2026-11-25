#!/usr/bin/env bash
# Starts Easy yt-dl-gui from source using the local .venv.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "No .venv found — run ./setup_env.sh first" >&2
  exit 1
fi
cd "$ROOT"
exec "$ROOT/.venv/bin/python" -m ytddlg "$@"
