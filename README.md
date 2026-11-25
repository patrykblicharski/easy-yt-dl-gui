<div align="center">

<img src="ytddlg/assets/logo.png" width="96" alt="Easy yt-dl-gui logo">

# Easy yt-dl-gui

**Download YouTube videos and audio in the best available quality — with a clean, simple desktop app.**

Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) · bundles FFmpeg and Deno · Windows & Linux

[![Latest release](https://img.shields.io/github/v/release/patrykblicharski/easy-yt-dl-gui?label=download&color=2563eb)](https://github.com/patrykblicharski/easy-yt-dl-gui/releases/latest)
[![Tests](https://github.com/patrykblicharski/easy-yt-dl-gui/actions/workflows/tests.yml/badge.svg)](https://github.com/patrykblicharski/easy-yt-dl-gui/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-7c3aed)
![Python](https://img.shields.io/badge/python-3.12-ea580c)

</div>

---

## Features

- 🎬 **Best video quality** — highest resolution and frame rate available (up to 4K/8K, 60 fps, HDR), merged
  without re-encoding into MKV or MP4. A *compatibility* mode prefers H.264/AAC for TVs, phones and editors.
- 🎵 **Best audio** — the original stream as-is (no quality loss), or converted to MP3, M4A, Opus, FLAC or WAV,
  with cover art and tags embedded.
- 📋 **Download list** — adding is separate from starting: collect links, then *Download all*. Parallel downloads
  (1–6), combined progress for video + audio streams, speed and ETA, retry, cancel. Unfinished tasks survive a restart.
- ▶ **One-click actions** on finished items: *Play*, *Show in folder*, *Delete* (to the Recycle Bin / Trash).
- 📚 **Playlists and channels** — pick the entries you want (click, Shift+click ranges, filter).
- ☰ **Manual format picker** — choose exact video and audio streams, like `yt-dlp -F`.
- 💬 **Subtitles** — chosen languages, embedded or as `.srt`, optionally auto-generated ones.
- ⏭ **SponsorBlock** — mark sponsor segments as chapters or cut them out.
- 🍪 **Cookies** from your browser or a `cookies.txt` file for age-restricted, private or members-only videos.
- 📎 **Clipboard watching** (optional) — copied YouTube links land on the list automatically.
- 🔔 Sound and taskbar flash when the list finishes, light/dark theme, duplicate warnings, keyboard shortcuts.
- 🛠 Every task logs the equivalent `yt-dlp` command — copy it from the context menu.

> The user interface is in **Polish**.

## Download

Grab the latest build from **[Releases](https://github.com/patrykblicharski/easy-yt-dl-gui/releases/latest)** —
everything is bundled (Python, yt-dlp, FFmpeg, Deno), nothing else to install.

| System | Package | How to run |
|---|---|---|
| **Windows 10/11** (x64) | `Easy-yt-dl-gui-v…-win64.zip` | Unzip and run `Easy yt-dl-gui.exe` |
| **Linux** (x64, glibc 2.35+) | `Easy-yt-dl-gui-v…-linux-x64.tar.gz` | `tar -xzf …` then `./easy-yt-dl-gui/easy-yt-dl-gui` |

On Linux, `./easy-yt-dl-gui/install-desktop-entry.sh` adds the app to your application menu
(`--uninstall` removes it).

> **Windows SmartScreen** may show *"Windows protected your PC"* because the app is not code-signed —
> click *More info → Run anyway*.

## Usage

1. Paste a YouTube link (video, playlist or channel) — it is analysed automatically.
2. Pick **▶ Wideo** (video) or **♫ Tylko audio** (audio only) and the quality / format.
3. Click **＋ Dodaj do listy** — *add to list* (`Ctrl+Enter`), add more links if you like.
4. Click **▶ Pobierz wszystkie** — *download all* (`Ctrl+D`).

Finished items show **▶ Odtwórz · ▤ Folder · ✕ Usuń** (*play · folder · delete*) right in the row;
right-click for more options.

| Shortcut | Action |
|---|---|
| `Ctrl+L` | Focus the link field |
| `F5` | Analyse the link |
| `Ctrl+Enter` | Add to the list |
| `Ctrl+D` | Download all added items |
| `Enter` / double-click | Start the selected item (or play it when finished) |
| `Delete` | Remove selected items from the list |
| `Ctrl+,` | Settings |

Settings live in `%APPDATA%\ytddlg` (Windows) or `~/.config/ytddlg` (Linux).

## Run from source

Requires **Python 3.10+** (3.12 recommended) with Tkinter.

**Windows**

```powershell
git clone https://github.com/patrykblicharski/easy-yt-dl-gui.git
cd easy-yt-dl-gui
powershell -ExecutionPolicy Bypass -File .\setup_env.ps1   # .venv + yt-dlp + FFmpeg + Deno
.\run.ps1
```

**Linux**

```bash
sudo apt install python3-venv python3-tk                    # Debian/Ubuntu; use your distro's equivalents
git clone https://github.com/patrykblicharski/easy-yt-dl-gui.git
cd easy-yt-dl-gui
./setup_env.sh
./run.sh
```

### Tests

```bash
python -m pytest -q tests                        # offline
YTDDLG_NETWORK=1 python -m pytest -q tests       # + real downloads from YouTube
```

### Build a package locally

```powershell
.\build_exe.ps1            # Windows → dist\Easy yt-dl-gui\ + release\*.zip
.\build_exe.ps1 -SelfTest  # also download a short test video with the built .exe
```

```bash
./build_linux.sh             # Linux → dist/easy-yt-dl-gui/ + release/*.tar.gz
./build_linux.sh --selftest
```

## Releases

Releases are built **on demand** by GitHub Actions — nothing is published automatically on push.

- **Actions → Release → Run workflow** (optionally set the version or mark it as a pre-release), or
- from a terminal: `gh workflow run release.yml` (`-f version=0.5.0` to override the version).

The workflow runs the tests, builds the Windows and Linux packages in parallel, checks that the bundled
tools work, and publishes a GitHub release with both archives and their SHA-256 checksums. The version comes
from `ytddlg/__init__.py` unless overridden.

## FAQ

<details>
<summary><b>Only low qualities (360p) are available / "n challenge solving failed"</b></summary>

yt-dlp needs a JavaScript runtime (Deno) to unlock higher qualities on YouTube. The release packages include it;
when running from source make sure `setup_env` finished and the header shows `deno ✓`.
</details>

<details>
<summary><b>"Sign in to confirm you're not a bot" / age-restricted or private videos</b></summary>

Open **⚙ Ustawienia → Cookies** (Settings) and choose your browser (Firefox works best on Windows — Chrome and Edge encrypt
their cookies in a way yt-dlp usually cannot read) or point to an exported `cookies.txt`.
</details>

<details>
<summary><b>A download suddenly stopped working</b></summary>

YouTube changes often. From source: click **⟳ yt-dlp** in the header to update yt-dlp. Release builds embed
yt-dlp — download the newest release.
</details>

<details>
<summary><b>Which format should I choose?</b></summary>

*Video → Best → MKV* gives the highest quality without re-encoding. If your player or TV struggles with AV1/VP9,
enable *Compatibility (H.264/AAC)* and/or pick MP4. For audio, *Original* keeps the source stream untouched;
choose MP3 only when you need it for a specific device.
</details>

## Legal

This tool is intended for downloading content you have the right to download — your own uploads,
Creative Commons or public-domain material, or content whose owner permits it. Respect copyright and
YouTube's Terms of Service. The authors take no responsibility for misuse.

Easy yt-dl-gui is not affiliated with YouTube or Google.

## Credits

Built on the shoulders of [yt-dlp](https://github.com/yt-dlp/yt-dlp), [FFmpeg](https://ffmpeg.org),
[Deno](https://deno.com), [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) and
[Pillow](https://python-pillow.org). Licenses of bundled components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Architecture notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

[MIT](LICENSE) © 2026 — created by **@blacha14**
