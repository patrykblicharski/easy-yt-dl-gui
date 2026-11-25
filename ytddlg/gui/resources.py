"""Resources (icon, logo) — work from source and in PyInstaller bundles, on Windows and Linux."""

from __future__ import annotations

import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
ICON = ASSETS / "ytddlg.ico"
LOGO = ASSETS / "logo.png"


def load_logo(size: int):
    """The logo as a CTkImage (or None when the file is missing)."""
    try:
        import customtkinter as ctk
        from PIL import Image

        img = Image.open(LOGO).convert("RGBA")
        return ctk.CTkImage(img, size=(size, size))
    except Exception:
        return None


def set_window_icon(window) -> None:
    """Sets the window icon. Windows: .ico file (CTk overrides the icon after ~200 ms, so it is
    set again). Linux/macOS: PNG via iconphoto (Tk cannot read .ico on X11)."""
    if sys.platform == "win32":
        if not ICON.exists():
            return

        def apply():
            try:
                window.iconbitmap(str(ICON))
            except Exception:
                pass

        apply()
        window.after(300, apply)
        return

    if not LOGO.exists():
        return
    try:
        import tkinter as tk

        photo = tk.PhotoImage(file=str(LOGO))
        window._ytddlg_icon = photo  # keep a reference so the image is not garbage-collected
        window.iconphoto(True, photo)
    except Exception:
        pass
