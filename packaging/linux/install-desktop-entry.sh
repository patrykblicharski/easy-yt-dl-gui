#!/usr/bin/env bash
# Adds Easy yt-dl-gui to the application menu (current user only, no sudo needed).
# Run from the extracted folder:  ./install-desktop-entry.sh
# Remove:                         ./install-desktop-entry.sh --uninstall
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/128x128/apps"
DESKTOP="$APPS/easy-yt-dl-gui.desktop"

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$DESKTOP" "$ICONS/easy-yt-dl-gui.png"
  echo "Menu entry removed."
  exit 0
fi

mkdir -p "$APPS" "$ICONS"
cp "$DIR/easy-yt-dl-gui.png" "$ICONS/easy-yt-dl-gui.png"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Easy yt-dl-gui
Comment=Download YouTube video and audio in the best quality
Comment[pl]=Pobieranie wideo i audio z YouTube w najlepszej jakości
Exec="$DIR/easy-yt-dl-gui"
Icon=easy-yt-dl-gui
Terminal=false
Categories=AudioVideo;Network;
StartupWMClass=Easy yt-dl-gui
EOF
chmod +x "$DESKTOP"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
echo "Added \"Easy yt-dl-gui\" to the application menu ($DESKTOP)."
