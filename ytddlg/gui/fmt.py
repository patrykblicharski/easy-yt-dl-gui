"""Number formatting for display."""

from __future__ import annotations


def human_bytes(n: float | None) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def human_speed(bps: float | None) -> str:
    return f"{human_bytes(bps)}/s" if bps else ""


def human_eta(sec: int | None) -> str:
    if sec is None:
        return ""
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def ellipsize(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"
