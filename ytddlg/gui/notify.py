"""Finished-list notification: system sound and a flashing taskbar button."""

from __future__ import annotations

import re
import sys

YOUTUBE_RE = re.compile(
    r"^https?://(www\.|m\.|music\.)?(youtube\.com/(watch\?|shorts/|playlist\?|live/|@)|youtu\.be/)\S+$",
    re.IGNORECASE,
)


def is_youtube_url(text: str) -> bool:
    return bool(YOUTUBE_RE.match(text.strip()))


def flash_window(window, count: int = 5) -> None:
    """Flashes the taskbar button until the user switches to the app (Windows only)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        FLASHW_ALL, FLASHW_TIMERNOFG = 0x3, 0xC
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, count, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


def play_done_sound(window=None) -> None:
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except ImportError:  # Linux/macOS — Tk window bell
        try:
            if window is not None:
                window.bell()
        except Exception:
            pass
    except Exception:
        pass


def notify_done(window) -> None:
    play_done_sound(window)
    try:
        focused = window.focus_displayof() is not None
    except Exception:
        focused = False
    if not focused:
        flash_window(window)
