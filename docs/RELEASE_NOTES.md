## Download

| System | File |
|---|---|
| Windows 10/11 (x64) | `Easy-yt-dl-gui-v…-win64.zip` |
| Linux (x64, glibc 2.35+ — Ubuntu 22.04, Debian 12, Fedora 36 and newer) | `Easy-yt-dl-gui-v…-linux-x64.tar.gz` |

Everything is bundled (Python, yt-dlp, FFmpeg, Deno) — nothing else to install.

**Windows:** unzip anywhere and run `Easy yt-dl-gui.exe`. SmartScreen may warn about an unknown publisher (the binary is not code-signed): *More info → Run anyway*.

**Linux:** `tar -xzf Easy-yt-dl-gui-v…-linux-x64.tar.gz && ./easy-yt-dl-gui/easy-yt-dl-gui`.
Optionally run `./easy-yt-dl-gui/install-desktop-entry.sh` to add it to your application menu.

Verify the download against the matching `.sha256` file (`Get-FileHash` on Windows, `sha256sum -c` on Linux).
