"""Application colour palette. Pairs are (light theme, dark theme)."""

from __future__ import annotations

# Accents
BRAND = ("#2563eb", "#1d4ed8")  # blue — header / logo
BRAND_DARK = ("#1e40af", "#1e3a8a")
ON_BRAND_MUTED = ("#dbeafe", "#bfdbfe")  # secondary text on the blue background
ON_BRAND_SOFT = ("#dbeafe", "#dbeafe")
ON_BRAND_HOVER = ("#bfdbfe", "#bfdbfe")
VIDEO = ("#7c3aed", "#8b5cf6")  # violet — video mode
VIDEO_HOVER = ("#6d28d9", "#7c3aed")
AUDIO = ("#ea580c", "#f97316")  # orange — audio mode
AUDIO_HOVER = ("#c2410c", "#ea580c")
SUCCESS = ("#16a34a", "#22c55e")
SUCCESS_HOVER = ("#15803d", "#16a34a")
DANGER = ("#dc2626", "#ef4444")
DANGER_HOVER = ("#b91c1c", "#dc2626")
INFO = ("#2563eb", "#3b82f6")
INFO_HOVER = ("#1d4ed8", "#2563eb")
WARNING = ("#d97706", "#f59e0b")

# Text
TEXT = ("gray10", "gray92")
MUTED = ("gray40", "gray62")
GREEN_TEXT = ("#15803d", "#4ade80")
RED_TEXT = ("#b91c1c", "#f87171")

# Surfaces
CARD = ("#ffffff", "#1f2330")
CARD_BORDER = ("#e5e7eb", "#2d3343")
WINDOW = ("#f3f4f8", "#151821")
FLAT_BTN = ("#e5e7eb", "#2b3040")
FLAT_HOVER = ("#d1d5db", "#363c4f")

# Table rows: tag -> (light background, dark background, light text, dark text)
ROW_COLORS = {
    "done": ("#e8f7ee", "#15291d", "#166534", "#86efac"),
    "error": ("#fdecec", "#33181b", "#991b1b", "#fca5a5"),
    "running": ("#e8f0fe", "#172338", "#1e40af", "#93c5fd"),
    "pending": ("#fff7e6", "#30281a", "#92400e", "#fcd34d"),
    "cancelled": (None, None, "gray50", "gray55"),
}
SELECTED = ("#c7d2fe", "#3730a3")  # selection (takes precedence over the state colour)
SELECTED_TEXT = ("#1e1b4b", "#ffffff")
HEADING = ("#eef0f6", "#262b3a")
TREE_BG = CARD

FLAT = {"fg_color": FLAT_BTN, "hover_color": FLAT_HOVER, "text_color": TEXT}


def mode_colors(mode: str) -> tuple:
    """(colour, hover colour) for the video/audio mode."""
    return (AUDIO, AUDIO_HOVER) if mode == "audio" else (VIDEO, VIDEO_HOVER)
