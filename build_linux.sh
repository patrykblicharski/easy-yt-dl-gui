#!/usr/bin/env bash
# Builds dist/easy-yt-dl-gui/easy-yt-dl-gui (one-folder build bundling ffmpeg, ffprobe and deno),
# runs the offline package check and packs it into release/Easy-yt-dl-gui-v<version>-linux-<arch>.tar.gz (+ .sha256).
# Usage:  ./build_linux.sh [--selftest] [--no-archive]
#   --selftest  also run the full self-test (probes and downloads a short YouTube video)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.venv/bin/python"
APP="easy-yt-dl-gui"
DIST="$ROOT/dist/$APP"
SELFTEST=0
ARCHIVE=1
for arg in "$@"; do
  case "$arg" in
    --selftest) SELFTEST=1 ;;
    --no-archive) ARCHIVE=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

VERSION="$("$PY" -c "import sys; sys.path.insert(0, '$ROOT'); import ytddlg; print(ytddlg.__version__)")"
case "$(uname -m)" in
  x86_64|amd64) ARCH_TAG="x64" ;;
  aarch64|arm64) ARCH_TAG="arm64" ;;
  *) ARCH_TAG="$(uname -m)" ;;
esac
echo "Version: $VERSION ($ARCH_TAG)"

"$PY" -m pip install --quiet --upgrade pyinstaller
"$PY" -m PyInstaller --noconfirm --clean "$ROOT/ytddlg.spec" \
  --distpath "$ROOT/dist" --workpath "$ROOT/build"

# Extras: licenses, icon and a helper that adds a launcher to the application menu
cp "$ROOT/LICENSE" "$DIST/LICENSE.txt"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$DIST/"
cp "$ROOT/ytddlg/assets/logo.png" "$DIST/easy-yt-dl-gui.png"
cp "$ROOT/packaging/linux/install-desktop-entry.sh" "$DIST/"
chmod +x "$DIST/$APP" "$DIST/install-desktop-entry.sh"
echo "Built: $DIST/$APP ($(du -sh "$DIST" | cut -f1))"

# Run the bundled app headless; settings go to a temp folder, never to ~/.config
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
YTDDLG_CONFIG_DIR="$TMP/config" "$DIST/$APP" --check "$TMP/check.json" || { cat "$TMP/check.json"; exit 1; }
echo "Package check: OK"

if [ "$SELFTEST" = 1 ]; then
  YTDDLG_CONFIG_DIR="$TMP/config" "$DIST/$APP" --selftest "$TMP/out" "$TMP/result.json" || { cat "$TMP/result.json"; exit 1; }
  echo "Self-test: OK"
fi

if [ "$ARCHIVE" = 1 ]; then
  mkdir -p "$ROOT/release"
  TAR="$ROOT/release/Easy-yt-dl-gui-v$VERSION-linux-$ARCH_TAG.tar.gz"
  rm -f "$TAR" "$TAR.sha256"
  tar -C "$ROOT/dist" -czf "$TAR" "$APP"
  (cd "$ROOT/release" && sha256sum "$(basename "$TAR")" > "$(basename "$TAR").sha256")
  echo "Package: $TAR ($(du -h "$TAR" | cut -f1))"
fi
