"""Locates external tools: ffmpeg, ffprobe, deno."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

EXE = ".exe" if sys.platform == "win32" else ""


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    # 1. When bundled with PyInstaller: the unpacked files directory and the exe directory
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            dirs.append(Path(sys._MEIPASS))  # type: ignore[attr-defined]
        dirs.append(Path(sys.executable).parent)
    # 2. The interpreter directory (.venv\Scripts or .venv/bin in a venv)
    dirs.append(Path(sys.executable).parent)
    # 3. The Scripts/bin directory of the current prefix (when the base python.exe was used)
    dirs.append(Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin"))
    seen: set[Path] = set()
    unique = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def find_tool(name: str) -> Path | None:
    """Looks next to the app/venv first, then on PATH."""
    for d in _candidate_dirs():
        p = d / f"{name}{EXE}"
        if p.is_file():
            return p
    found = shutil.which(name)
    return Path(found) if found else None


@dataclass(frozen=True)
class Tools:
    ffmpeg: Path | None
    ffprobe: Path | None
    deno: Path | None

    @property
    def missing(self) -> list[str]:
        return [n for n in ("ffmpeg", "ffprobe", "deno") if getattr(self, n) is None]

    @property
    def ok(self) -> bool:
        return not self.missing


def detect_tools() -> Tools:
    return Tools(ffmpeg=find_tool("ffmpeg"), ffprobe=find_tool("ffprobe"), deno=find_tool("deno"))
