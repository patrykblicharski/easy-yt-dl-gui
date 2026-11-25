"""File operations: moving files to the Recycle Bin / Trash."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def move_to_trash(path: Path) -> None:
    """Moves a file to the Recycle Bin / Trash. Raises OSError on failure.

    Windows: SHFileOperationW with FOF_ALLOWUNDO (the file can be restored).
    Linux/macOS: see _trash_posix.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    if sys.platform != "win32":
        _trash_posix(path)
        return

    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = str(path.resolve()) + "\0"  # double-NUL terminated list (ctypes adds the second one)
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc != 0 or op.fAnyOperationsAborted:
        raise OSError(f"Nie udało się przenieść do Kosza (kod {rc}): {path}")
    if path.exists():
        raise OSError(f"Plik nadal istnieje: {path}")


def _trash_posix(path: Path) -> None:
    """Linux/macOS: `gio trash`, falling back to the freedesktop.org Trash specification."""
    import shutil
    import subprocess
    from datetime import datetime
    from urllib.parse import quote

    gio = shutil.which("gio")
    if gio and subprocess.run([gio, "trash", str(path)], capture_output=True).returncode == 0:
        return
    if sys.platform == "darwin":
        trash = Path.home() / ".Trash"
        trash.mkdir(exist_ok=True)
        shutil.move(str(path), str(_unique(trash / path.name)))
        return
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "Trash"
    files, info = base / "files", base / "info"
    files.mkdir(parents=True, exist_ok=True)
    info.mkdir(parents=True, exist_ok=True)
    target = _unique(files / path.name)
    (info / f"{target.name}.trashinfo").write_text(
        "[Trash Info]\n"
        f"Path={quote(str(path.resolve()))}\n"
        f"DeletionDate={datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n",
        encoding="utf-8",
    )
    shutil.move(str(path), str(target))


def _unique(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(2, 10_000):
        q = p.with_name(f"{p.stem}.{i}{p.suffix}")
        if not q.exists():
            return q
    raise OSError(f"Brak wolnej nazwy w koszu dla {p.name}")


def related_files(path: Path) -> list[Path]:
    """The result file plus companion files sharing its base name (e.g. .srt subtitles)."""
    path = Path(path)
    out = [path] if path.exists() else []
    stem = path.stem
    try:
        for p in path.parent.iterdir():
            if p != path and p.name.startswith(stem + ".") and p.suffix.lower() in (".srt", ".vtt", ".ass"):
                out.append(p)
    except OSError:
        pass
    return out


def is_same_file(a: os.PathLike | None, b: os.PathLike | None) -> bool:
    try:
        return a is not None and b is not None and Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False
