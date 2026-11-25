import ast
import sys
from pathlib import Path

import ytddlg
from ytddlg.gui import fontfix

# Symbols that fontconfig on Ubuntu draws with "Noto Color Emoji" — they crashed Tk/Xft in 0.5.0 test builds
EMOJI_FONT_SYMBOLS = {"⏭", "⌛"}


def test_applies_on_linux(tmp_path, monkeypatch):
    monkeypatch.setattr(fontfix.sys, "platform", "linux")
    monkeypatch.setenv("FONTCONFIG_FILE", "x")  # registers the variable so monkeypatch restores it afterwards
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    monkeypatch.delenv("YTDDLG_KEEP_COLOR_FONTS", raising=False)
    system = tmp_path / "system-fonts.conf"
    system.write_text("<fontconfig/>", encoding="utf-8")
    monkeypatch.setattr(fontfix, "SYSTEM_CONF", str(system))
    path = fontfix.avoid_color_emoji_fonts(tmp_path / "cfg")
    assert path == tmp_path / "cfg" / "fonts.conf"
    assert fontfix.os.environ["FONTCONFIG_FILE"] == str(path)
    text = path.read_text(encoding="utf-8")
    assert str(system) in text and "<rejectfont>" in text and 'name="color"' in text
    # unchanged content is not rewritten
    mtime = path.stat().st_mtime_ns
    monkeypatch.delenv("FONTCONFIG_FILE")
    fontfix.avoid_color_emoji_fonts(tmp_path / "cfg")
    assert path.stat().st_mtime_ns == mtime


def test_respects_user_config_and_opt_out(tmp_path, monkeypatch):
    monkeypatch.setattr(fontfix.sys, "platform", "linux")
    monkeypatch.setenv("FONTCONFIG_FILE", "/home/me/fonts.conf")
    assert fontfix.avoid_color_emoji_fonts(tmp_path) is None
    monkeypatch.delenv("FONTCONFIG_FILE")
    monkeypatch.setenv("YTDDLG_KEEP_COLOR_FONTS", "1")
    assert fontfix.avoid_color_emoji_fonts(tmp_path) is None


def test_noop_outside_linux(tmp_path, monkeypatch):
    monkeypatch.setattr(fontfix.sys, "platform", "win32")
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    assert fontfix.avoid_color_emoji_fonts(tmp_path) is None
    assert "FONTCONFIG_FILE" not in fontfix.os.environ


def test_ui_avoids_emoji_font_symbols():
    pkg = Path(ytddlg.__file__).parent
    found = []
    for path in pkg.rglob("*.py"):
        if path.name == "fontfix.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                bad = EMOJI_FONT_SYMBOLS & set(node.value)
                if bad:
                    found.append(f"{path.name}:{node.lineno}: {''.join(bad)}")
    assert not found, found


def test_fontfix_runs_before_tk_window():
    """avoid_color_emoji_fonts() must be called before CTk.__init__ creates the Tk interpreter."""
    src = (Path(ytddlg.__file__).parent / "gui" / "app.py").read_text(encoding="utf-8")
    assert src.index("avoid_color_emoji_fonts(config_dir())") < src.index("super().__init__(fg_color=theme.WINDOW)")
    assert sys.modules  # keep pytest from flagging an import-only module
