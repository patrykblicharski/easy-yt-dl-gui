"""Workaround for a Tk crash on Linux with colour emoji fonts.

Tk on X11 renders text through Xft. When fontconfig falls back to a colour bitmap font such as
"Noto Color Emoji" for a symbol (e.g. ⏭ or ⌛ on Ubuntu), later font operations can segfault the whole
process. For this process only, fontconfig is told to reject colour fonts; symbols then come from regular
fonts (or show as a box), the system configuration is otherwise untouched.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SYSTEM_CONF = "/etc/fonts/fonts.conf"

FONTS_CONF = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<!-- Written by Easy yt-dl-gui: the system configuration plus "no colour fonts" (Tk/Xft crash workaround). -->
<fontconfig>
  <include ignore_missing="yes">{system}</include>
  <selectfont>
    <rejectfont>
      <pattern><patelt name="color"><bool>true</bool></patelt></pattern>
    </rejectfont>
  </selectfont>
</fontconfig>
"""


def avoid_color_emoji_fonts(config_dir: Path) -> Path | None:
    """Points FONTCONFIG_FILE at a config that rejects colour fonts. Must run before Tk starts.

    Does nothing outside Linux, when FONTCONFIG_FILE is already set by the user, or when
    YTDDLG_KEEP_COLOR_FONTS=1. Returns the config path when it was applied.
    """
    if not sys.platform.startswith("linux"):
        return None
    if os.environ.get("FONTCONFIG_FILE") or os.environ.get("YTDDLG_KEEP_COLOR_FONTS") == "1":
        return None
    if not os.path.isfile(SYSTEM_CONF):
        return None
    content = FONTS_CONF.format(system=SYSTEM_CONF)
    path = config_dir / "fonts.conf"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
    except OSError:
        return None
    os.environ["FONTCONFIG_FILE"] = str(path)
    return path
