"""Application settings stored in %APPDATA%\\ytddlg\\settings.json (~/.config/ytddlg on Linux)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import APP_NAME
from .core.options import DEFAULT_TEMPLATE, MODE_VIDEO, SB_DEFAULT_CATEGORIES, SB_OFF, NetOptions, migrate_ids


def config_dir() -> Path:
    """Settings folder. YTDDLG_CONFIG_DIR overrides the location (tests, portable use)."""
    override = os.environ.get("YTDDLG_CONFIG_DIR")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def queue_file() -> Path:
    return config_dir() / "queue.json"


def default_out_dir() -> str:
    return str(Path.home() / "Downloads" / APP_NAME)


@dataclass
class Settings:
    out_dir: str = ""
    mode: str = MODE_VIDEO
    language: str = ""  # "pl" / "en"; empty = system language
    video_quality: str = "best"
    container: str = "MKV"
    compat: bool = False
    audio_format: str = "best"
    audio_quality: str = "0"
    template: str = DEFAULT_TEMPLATE
    max_parallel: int = 2
    appearance: str = "System"  # System / Dark / Light
    auto_paste: bool = True
    autostart: bool = False  # start a task right after it is added
    restore_queue: bool = True  # restore unfinished tasks on startup
    verbose_log: bool = False
    notify_done: bool = True  # sound + taskbar flash when the list finishes
    watch_clipboard: bool = False  # copied YouTube links go straight to the list
    geometry: str = "1080x800"
    # --- version 2 ---
    subs: bool = False
    sub_langs: str = "pl,en"
    sub_auto: bool = False
    sub_embed: bool = True
    sponsorblock: str = SB_OFF
    sb_categories: str = SB_DEFAULT_CATEGORIES
    cookies_browser: str = ""
    cookies_file: str = ""
    rate_limit: str = ""

    def __post_init__(self) -> None:
        if not self.out_dir:
            self.out_dir = default_out_dir()

    def net(self) -> NetOptions:
        return NetOptions(
            cookies_browser=self.cookies_browser, cookies_file=self.cookies_file, rate_limit=self.rate_limit
        )

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or config_dir() / "settings.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        migrate_ids(data)  # labels saved by versions <= 0.4
        known = {f.name: f for f in fields(cls)}
        clean = {}
        defaults = cls()
        for k, v in data.items():
            if k in known and type(v) is type(getattr(defaults, k)):
                clean[k] = v
        return cls(**clean)

    def save(self, path: Path | None = None) -> None:
        path = path or config_dir() / "settings.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
