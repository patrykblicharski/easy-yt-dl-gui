# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: one-folder build bundling ffmpeg, ffprobe and deno.
#   Windows: .\build_exe.ps1     -> dist\Easy yt-dl-gui\Easy yt-dl-gui.exe
#   Linux:   ./build_linux.sh    -> dist/easy-yt-dl-gui/easy-yt-dl-gui
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = os.path.abspath(SPECPATH)
WINDOWS = sys.platform == "win32"
BIN_DIR = os.path.join(ROOT, ".venv", "Scripts" if WINDOWS else "bin")
EXT = ".exe" if WINDOWS else ""
APP = "Easy yt-dl-gui" if WINDOWS else "easy-yt-dl-gui"

binaries = []
for tool in ("ffmpeg", "ffprobe", "deno"):
    path = os.path.join(BIN_DIR, tool + EXT)
    if not os.path.isfile(path):
        raise SystemExit(f"Missing {path} — run the setup_env script first")
    binaries.append((path, "."))

datas = [(os.path.join(ROOT, "ytddlg", "assets"), os.path.join("ytddlg", "assets"))]
datas += collect_data_files("customtkinter")
datas += collect_data_files("yt_dlp_ejs")
hiddenimports = ["yt_dlp_ejs"]

# curl_cffi ships a native library and data (browser impersonation)
cc_datas, cc_bins, cc_hidden = collect_all("curl_cffi")
datas += cc_datas
binaries += cc_bins
hiddenimports += cc_hidden

a = Analysis(
    [os.path.join(ROOT, "ytddlg_app.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "static_ffmpeg", "twine", "docutils", "IPython", "matplotlib", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP,
    console=False,
    icon=os.path.join(ROOT, "ytddlg", "assets", "ytddlg.ico") if WINDOWS else None,
    upx=False,
    strip=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP, upx=False)
