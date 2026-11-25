"""Minimal i18n: English source strings in code, translations in dictionaries.

Usage:  t("Added {n} items", n=3)   — returns the text in the current language, formatted.
The language is set once at startup (`set_language`); switching it restarts the app.
"""

from __future__ import annotations

import locale
import os

from .i18n_pl import PL

LANGUAGES = {"pl": "Polski", "en": "English"}
_TRANSLATIONS = {"pl": PL}
_current = "en"


def detect_language() -> str:
    """System language if supported, otherwise English."""
    candidates = [os.environ.get(k, "") for k in ("LC_ALL", "LC_MESSAGES", "LANG")]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    if os.name == "nt":
        try:
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if lang_id & 0x3FF == 0x15:  # LANG_POLISH
                return "pl"
        except Exception:
            pass
    for c in candidates:
        c = c.lower()
        if c.startswith("pl") or c.startswith("polish"):
            return "pl"
    return "en"


def set_language(code: str) -> str:
    """Sets the current language (empty/unknown = auto-detect). Returns the code in use."""
    global _current
    _current = code if code in LANGUAGES else detect_language()
    return _current


def get_language() -> str:
    return _current


def t(text: str, **kwargs) -> str:
    """Translates `text` into the current language and fills `{placeholders}`."""
    out = _TRANSLATIONS.get(_current, {}).get(text, text)
    return out.format(**kwargs) if kwargs else out
