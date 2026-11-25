#!/usr/bin/env bash
# Sets up the development environment on Linux: .venv + yt-dlp + ffmpeg/ffprobe + deno (all in .venv/bin)
# Requires python3 (3.10+) with venv and tkinter, e.g. on Debian/Ubuntu:
#   sudo apt install python3-venv python3-tk
# Usage:  ./setup_env.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  "${PYTHON:-python3}" -m venv "$VENV"
fi
"$PY" -m pip install --upgrade pip
"$PY" -m pip install --upgrade -r "$ROOT/requirements.txt"

# Static ffmpeg/ffprobe builds -> .venv/bin (next to the interpreter, on PATH once the venv is active)
"$PY" - "$VENV/bin" <<'EOF'
import shutil, sys
import static_ffmpeg.run as r
for p in r.get_or_fetch_platform_executables_else_raise():
    shutil.copy2(p, sys.argv[1])
EOF

"$PY" -c "import tkinter" 2>/dev/null || echo "WARNING: tkinter is missing — install the python3-tk package"
echo "yt-dlp : $("$VENV/bin/yt-dlp" --version)"
echo "ffmpeg : $("$VENV/bin/ffmpeg" -hide_banner -version | head -n1)"
echo "deno   : $("$VENV/bin/deno" --version | head -n1)"
