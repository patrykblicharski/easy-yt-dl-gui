"""Main application window (CustomTkinter)."""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import yt_dlp.version
from PIL import Image

from .. import APP_TITLE, AUTHOR, __version__
from ..config import Settings, default_out_dir, queue_file
from ..core.options import (
    AUDIO_FORMATS,
    AUDIO_QUALITIES,
    CONTAINERS,
    LANGS_RE,
    LOSSY_AUDIO,
    MODE_AUDIO,
    MODE_VIDEO,
    SB_MARK,
    SB_REMOVE,
    SPONSORBLOCK_MODES,
    VIDEO_QUALITIES,
    DownloadRequest,
    audio_format_label,
    audio_quality_label,
    command_line,
    sponsorblock_label,
    video_quality_label,
)
from ..core.probe import Entry, ProbeResult, probe
from ..core.queue import DownloadQueue, State, Task, short_error
from ..core.tools import detect_tools
from ..i18n import LANGUAGES, get_language, set_language
from ..i18n import t as tr
from . import theme
from .dialogs import FormatDialog, PlaylistDialog, SettingsDialog
from .fmt import ellipsize, human_speed
from .notify import is_youtube_url, notify_done
from .queue_view import QueueView, open_path
from .resources import load_logo, set_window_icon

APPEARANCE_MODES = ["System", "Dark", "Light"]
URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
THUMB_SIZE = (176, 99)
MAX_LOG_LINES = 3000
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FLAT = theme.FLAT
GRAY, GREEN, RED = theme.MUTED, theme.GREEN_TEXT, theme.RED_TEXT
ON_BRAND = {"fg_color": ("#ffffff", "#ffffff"), "hover_color": theme.ON_BRAND_HOVER, "text_color": theme.BRAND_DARK}


def dup_key(req: DownloadRequest) -> tuple:
    """Tasks with the same key would write to the same file."""
    target = req.container if req.mode == MODE_VIDEO else req.audio_format
    return (req.url.strip(), req.mode, target, req.format_override)


class Choice:
    """An option menu value: shows translated labels, stores language-independent ids."""

    def __init__(self, ids, label_fn, current: str, default: str):
        self.labels = {i: label_fn(i) for i in ids}
        self.ids = {v: k for k, v in self.labels.items()}
        self.var = ctk.StringVar(value=self.labels.get(current, self.labels[default]))

    @property
    def values(self) -> list[str]:
        return list(self.labels.values())

    def get(self) -> str:
        return self.ids[self.var.get()]


def restart_command() -> list[str]:
    """Command that starts this application again (bundled or from source)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "ytddlg"]


class App(ctk.CTk):
    def __init__(self, settings: Settings | None = None, restore: bool = True) -> None:
        self.settings = settings or Settings.load()
        set_language(self.settings.language)
        ctk.set_appearance_mode(self.settings.appearance)
        super().__init__(fg_color=theme.WINDOW)
        self.title(f"{APP_TITLE} {__version__}  ·  by {AUTHOR}")
        self.geometry(self.settings.geometry)
        self.minsize(1000, 700)
        set_window_icon(self)

        self.tools = detect_tools()
        self.dq = DownloadQueue(self.tools, max_parallel=self.settings.max_parallel, verbose=self.settings.verbose_log)
        self.ui_events: "queue.Queue[tuple]" = queue.Queue()
        self.probe_result: ProbeResult | None = None
        self.probe_input: str = ""  # URL typed by the user that probe_result belongs to
        self._probing: str | None = None
        self._add_after_probe = False
        self._last_auto_paste = ""
        self._log_visible = False
        self._queue_dirty = False
        self._updating = False
        self._restart_requested = False
        self.mode_labels = {MODE_VIDEO: "▶ " + tr("Video"), MODE_AUDIO: "♫ " + tr("Audio only")}

        self._build()
        self._apply_mode(self.settings.mode)
        self._report_tools()

        if restore and self.settings.restore_queue:
            n = self.dq.load(queue_file())
            if n:
                self.log("info", tr("Restored {n} unfinished tasks from the previous session.", n=n))

        self._was_active = False
        self._speed_shown_at = 0.0
        try:
            self._clip_seen = self.clipboard_get().strip()  # do not add whatever was already in the clipboard
        except Exception:
            self._clip_seen = ""
        self._bind_shortcuts()
        self._clip_job = self.after(1000, self._watch_clipboard)

        self._app_has_focus = False
        self.bind("<FocusIn>", self._on_focus)
        self.bind("<FocusOut>", self._on_focus_out)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_id = self.after(100, self._poll)

    # ======================================================================
    # UI construction
    # ======================================================================
    def _card(self, row: int, **kw) -> ctk.CTkFrame:
        f = ctk.CTkFrame(self, fg_color=theme.CARD, border_width=1, border_color=theme.CARD_BORDER, corner_radius=12)
        f.grid(row=row, column=0, sticky="ew", padx=14, pady=kw.get("pady", 5))
        return f

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        s = self.settings
        brand_menu = {
            "height": 26, "corner_radius": 7, "fg_color": "white", "button_color": theme.ON_BRAND_SOFT,
            "button_hover_color": theme.ON_BRAND_HOVER, "text_color": theme.BRAND_DARK,
            "dropdown_fg_color": theme.CARD, "dropdown_text_color": theme.TEXT,
        }

        # --- Header (compact, single line) ----------------------------------
        header = ctk.CTkFrame(self, fg_color=theme.BRAND, corner_radius=0, height=40)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(3, weight=1)
        logo = load_logo(24)
        ctk.CTkLabel(header, text="", image=logo, width=26, height=26).grid(row=0, column=0, padx=(12, 6), pady=6)
        ctk.CTkLabel(
            header, text=APP_TITLE, font=ctk.CTkFont(size=15, weight="bold"), text_color="white", height=26
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            header, text=f"by {AUTHOR}", font=ctk.CTkFont(size=11), text_color=theme.ON_BRAND_MUTED, height=26
        ).grid(row=0, column=2, sticky="sw", padx=(8, 0), pady=(0, 7))
        self.pills = ctk.CTkFrame(header, fg_color="transparent")
        self.pills.grid(row=0, column=3, sticky="e", padx=8)
        ctk.CTkButton(
            header, text="⚙ " + tr("Settings"), width=96, height=26, corner_radius=7, command=self.open_settings,
            **ON_BRAND,
        ).grid(row=0, column=4, padx=(0, 5))
        self.update_btn = ctk.CTkButton(
            header, text="⟳ yt-dlp", width=74, height=26, corner_radius=7, command=self.update_ytdlp, **ON_BRAND
        )
        self.update_btn.grid(row=0, column=5, padx=(0, 5))
        self.lang_choice = Choice(list(LANGUAGES), lambda c: LANGUAGES[c], get_language(), "en")
        ctk.CTkOptionMenu(
            header, values=self.lang_choice.values, variable=self.lang_choice.var, width=92,
            command=self._on_language, **brand_menu,
        ).grid(row=0, column=6, padx=(0, 5))
        self.appearance_choice = Choice(APPEARANCE_MODES, tr, s.appearance, "System")
        ctk.CTkOptionMenu(
            header, values=self.appearance_choice.values, variable=self.appearance_choice.var, width=92,
            command=self._on_appearance, **brand_menu,
        ).grid(row=0, column=7, padx=(0, 12))

        # --- URL -----------------------------------------------------------
        url_row = ctk.CTkFrame(self, fg_color="transparent")
        url_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(12, 4))
        url_row.grid_columnconfigure(0, weight=1)
        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(
            url_row, textvariable=self.url_var, height=38, corner_radius=10, border_width=2,
            border_color=theme.CARD_BORDER, fg_color=theme.CARD, font=ctk.CTkFont(size=14),
            placeholder_text=tr("Paste a link to a YouTube video, playlist or channel…"),
        )
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.url_entry.bind("<Return>", lambda e: self.analyze())
        self.url_entry.bind("<<Paste>>", lambda e: self.after(50, self._analyze_if_url))
        self.url_entry.bind("<FocusIn>", lambda e: self.url_entry.configure(border_color=theme.INFO), add="+")
        self.url_entry.bind("<FocusOut>", lambda e: self.url_entry.configure(border_color=theme.CARD_BORDER), add="+")
        ctk.CTkButton(
            url_row, text=tr("Paste"), width=90, height=38, corner_radius=10, command=self.paste_and_analyze, **FLAT
        ).grid(row=0, column=1, padx=(8, 0))
        self.analyze_btn = ctk.CTkButton(
            url_row, text=tr("Analyze"), width=110, height=38, corner_radius=10, command=self.analyze,
            fg_color=theme.INFO, hover_color=theme.INFO_HOVER, font=ctk.CTkFont(weight="bold"),
        )
        self.analyze_btn.grid(row=0, column=2, padx=(8, 0))

        # --- Video info card ---------------------------------------------
        info = self._card(2)
        self.info_card = info
        info.grid_columnconfigure(2, weight=1)
        self.mode_stripe = ctk.CTkFrame(info, width=5, corner_radius=3, fg_color=theme.VIDEO)
        self.mode_stripe.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(8, 0), pady=10)
        self._blank_thumb = ctk.CTkImage(Image.new("RGB", THUMB_SIZE, (90, 90, 110)), size=THUMB_SIZE)
        self.thumb_lbl = ctk.CTkLabel(info, text="", image=self._blank_thumb, width=THUMB_SIZE[0], corner_radius=8)
        self.thumb_lbl.grid(row=0, column=1, rowspan=3, padx=10, pady=10)
        self.title_lbl = ctk.CTkLabel(
            info, text=tr("No link analysed yet"), anchor="w", justify="left",
            font=ctk.CTkFont(size=16, weight="bold"), wraplength=600,
        )
        self.title_lbl.grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=(12, 0))
        self.details_lbl = ctk.CTkLabel(info, text="", anchor="w", justify="left", text_color=GRAY, wraplength=600)
        self.details_lbl.grid(row=1, column=2, sticky="ew", padx=(0, 10))
        self.probe_status = ctk.CTkLabel(info, text="", anchor="w", justify="left", wraplength=600)
        self.probe_status.grid(row=2, column=2, sticky="new", padx=(0, 10), pady=(0, 10))
        self.formats_btn = ctk.CTkButton(
            info, text="☰ " + tr("Formats…"), width=104, height=32, state="disabled", command=self.open_formats, **FLAT
        )
        self.formats_btn.grid(row=0, column=3, rowspan=3, padx=(0, 14))
        info.bind("<Configure>", self._on_info_resize)
        # "Analyzing" bar — visible only while probing
        self.probe_bar = ctk.CTkProgressBar(
            info, mode="indeterminate", height=6, corner_radius=3, progress_color=theme.INFO,
            fg_color=theme.FLAT_BTN, indeterminate_speed=1.2,
        )
        self._busy_thumb = self._make_busy_thumb()
        self._busy_job: str | None = None
        self._busy_started = 0.0

        # --- Options ---------------------------------------------------------
        opts = self._card(3)
        opts.grid_columnconfigure(1, weight=1)

        self.mode_seg = ctk.CTkSegmentedButton(
            opts, values=list(self.mode_labels.values()), command=self._on_mode_label, height=34,
            font=ctk.CTkFont(size=13, weight="bold"), unselected_color=theme.FLAT_BTN,
            unselected_hover_color=theme.FLAT_HOVER, fg_color=theme.FLAT_BTN, text_color=theme.TEXT,
        )
        self.mode_seg.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        menu_kw = {"fg_color": theme.FLAT_BTN, "button_color": theme.FLAT_HOVER,
                   "button_hover_color": theme.FLAT_HOVER, "text_color": theme.TEXT}
        # Video options
        self.video_frame = ctk.CTkFrame(opts, fg_color="transparent")
        ctk.CTkLabel(self.video_frame, text=tr("Quality:")).pack(side="left", padx=(4, 4))
        self.vq = Choice(VIDEO_QUALITIES, video_quality_label, s.video_quality, "best")
        ctk.CTkOptionMenu(
            self.video_frame, values=self.vq.values, variable=self.vq.var, width=124,
            command=self._save_opts, **menu_kw,
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(self.video_frame, text=tr("Container:")).pack(side="left", padx=(0, 4))
        self.cont_var = ctk.StringVar(value=s.container if s.container in CONTAINERS else "MKV")
        ctk.CTkOptionMenu(
            self.video_frame, values=CONTAINERS, variable=self.cont_var, width=76, command=self._save_opts, **menu_kw
        ).pack(side="left", padx=(0, 12))
        self.compat_var = ctk.BooleanVar(value=s.compat)
        self.compat_cb = ctk.CTkCheckBox(
            self.video_frame, text=tr("Compatibility (H.264/AAC)"), variable=self.compat_var, command=self._save_opts
        )
        self.compat_cb.pack(side="left")

        # Audio options
        self.audio_frame = ctk.CTkFrame(opts, fg_color="transparent")
        ctk.CTkLabel(self.audio_frame, text=tr("Format:")).pack(side="left", padx=(4, 4))
        self.af = Choice(AUDIO_FORMATS, audio_format_label, s.audio_format, "best")
        ctk.CTkOptionMenu(
            self.audio_frame, values=self.af.values, variable=self.af.var, width=230,
            command=self._save_opts, **menu_kw,
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(self.audio_frame, text=tr("Quality:")).pack(side="left", padx=(0, 4))
        self.aq = Choice(AUDIO_QUALITIES, audio_quality_label, s.audio_quality, "0")
        self.aq_menu = ctk.CTkOptionMenu(
            self.audio_frame, values=self.aq.values, variable=self.aq.var, width=150,
            command=self._save_opts, **menu_kw,
        )
        self.aq_menu.pack(side="left")

        # Extras: subtitles + SponsorBlock
        extras = ctk.CTkFrame(opts, fg_color="transparent")
        extras.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 0))
        self.subs_frame = ctk.CTkFrame(extras, fg_color="transparent")
        self.subs_var = ctk.BooleanVar(value=s.subs)
        self.subs_cb = ctk.CTkCheckBox(
            self.subs_frame, text=tr("Subtitles:"), variable=self.subs_var, command=self._save_opts, width=80
        )
        self.subs_cb.pack(side="left")
        self.langs_var = ctk.StringVar(value=s.sub_langs)
        self.langs_var.trace_add("write", lambda *a: self._save_opts())
        self.langs_entry = ctk.CTkEntry(self.subs_frame, textvariable=self.langs_var, width=90, height=28)
        self.langs_entry.pack(side="left", padx=(4, 18))
        self.subs_frame.pack(side="left")
        self.sb_label = ctk.CTkLabel(extras, text="⏭ SponsorBlock:")
        self.sb_label.pack(side="left", padx=(0, 4))
        self.sb = Choice(SPONSORBLOCK_MODES, sponsorblock_label, s.sponsorblock, "off")
        ctk.CTkOptionMenu(
            extras, values=self.sb.values, variable=self.sb.var, width=190, command=self._save_opts, **menu_kw
        ).pack(side="left")

        self.opts_hint = ctk.CTkLabel(opts, text="", anchor="w", justify="left", text_color=GRAY, wraplength=900)
        self.opts_hint.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(6, 4))

        # Folder + add button (same card)
        folder = ctk.CTkFrame(opts, fg_color="transparent")
        folder.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(2, 12))
        folder.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(folder, text=tr("Folder:")).grid(row=0, column=0, padx=(2, 8))
        self.dir_var = ctk.StringVar(value=s.out_dir)
        ctk.CTkEntry(folder, textvariable=self.dir_var, height=32).grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(folder, text=tr("Browse…"), width=86, height=32, command=self.choose_dir, **FLAT).grid(
            row=0, column=2, padx=(8, 0)
        )
        ctk.CTkButton(folder, text=tr("Open"), width=74, height=32, command=self.open_dir, **FLAT).grid(
            row=0, column=3, padx=(8, 0)
        )
        self.add_btn = ctk.CTkButton(
            folder, text="＋ " + tr("Add to list"), width=170, height=34, corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"), command=self.add,
        )
        self.add_btn.grid(row=0, column=4, padx=(14, 0))

        # --- Queue -----------------------------------------------------------
        self.queue_view = QueueView(self, self.dq, on_parallel=self._on_parallel, parallel=s.max_parallel)
        self.queue_view.grid(row=5, column=0, sticky="nsew", padx=14, pady=(10, 4))

        # --- Bottom bar + log ---------------------------------------------------
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 8))
        bottom.grid_columnconfigure(1, weight=1)
        self.log_btn = ctk.CTkButton(bottom, text="▸ Log", width=70, height=26, command=self.toggle_log, **FLAT)
        self.log_btn.grid(row=0, column=0)
        self.status_lbl = ctk.CTkLabel(bottom, text="", anchor="w", text_color=GRAY)
        self.status_lbl.grid(row=0, column=1, sticky="ew", padx=12)
        self.speed_lbl = ctk.CTkLabel(bottom, text="", anchor="e", text_color=theme.INFO, font=ctk.CTkFont(weight="bold"))
        self.speed_lbl.grid(row=0, column=2, sticky="e", padx=(0, 12))
        ctk.CTkLabel(
            bottom, text=tr("Ctrl+L link · F5 analyze · Ctrl+Enter add · Ctrl+D download"),
            text_color=GRAY, font=ctk.CTkFont(size=11),
        ).grid(row=0, column=3, sticky="e")

        self.log_box = ctk.CTkTextbox(
            self, height=150, wrap="word",
            font=ctk.CTkFont(family="Consolas" if sys.platform == "win32" else "DejaVu Sans Mono", size=12),
            fg_color=theme.CARD, border_width=1, border_color=theme.CARD_BORDER,
        )
        self.log_box.tag_config("error", foreground="#ef4444")
        self.log_box.tag_config("warning", foreground="#f59e0b")
        self.log_box.tag_config("debug", foreground="gray55")
        self.log_box.configure(state="disabled")

    def _on_info_resize(self, event) -> None:
        wrap = max(300, event.width - THUMB_SIZE[0] - 190)
        for lbl in (self.title_lbl, self.details_lbl, self.probe_status):
            lbl.configure(wraplength=wrap)

    def _make_busy_thumb(self) -> ctk.CTkImage:
        """Placeholder thumbnail while probing: blue background with the logo."""
        w, h = THUMB_SIZE
        light = Image.new("RGB", (w, h), (219, 234, 254))
        dark = Image.new("RGB", (w, h), (30, 58, 138))
        try:
            from .resources import LOGO

            logo = Image.open(LOGO).convert("RGBA").resize((56, 56), Image.LANCZOS)
            for im in (light, dark):
                im.paste(logo, ((w - 56) // 2, (h - 56) // 2), logo)
        except Exception:
            pass
        return ctk.CTkImage(light_image=light, dark_image=dark, size=THUMB_SIZE)

    def _set_busy(self, on: bool, url: str = "") -> None:
        """Clear "analyzing" state: blue card border, animated bar, seconds counter."""
        if self._busy_job is not None:
            self.after_cancel(self._busy_job)
            self._busy_job = None
        if on:
            self._busy_started = time.monotonic()
            self.info_card.configure(border_color=theme.INFO, border_width=2)
            self.url_entry.configure(border_color=theme.INFO)
            self.thumb_lbl.configure(image=self._busy_thumb)
            self.title_lbl.configure(text_color=theme.INFO)
            self.details_lbl.configure(text=ellipsize(url, 120))
            self.probe_bar.grid(row=3, column=1, columnspan=3, sticky="ew", padx=(10, 14), pady=(0, 10))
            self.probe_bar.start()
            self.set_status("⌛ " + tr("Analyzing the link…"), theme.INFO)
            self._busy_tick(0)
        else:
            self.probe_bar.stop()
            self.probe_bar.grid_remove()
            self.info_card.configure(border_color=theme.CARD_BORDER, border_width=1)
            self.url_entry.configure(border_color=theme.CARD_BORDER)
            self.title_lbl.configure(text_color=theme.TEXT)
            self.analyze_btn.configure(state="normal", text=tr("Analyze"))
            self.set_status("")

    def _busy_tick(self, n: int) -> None:
        dots = "." * (n % 4)
        secs = int(time.monotonic() - self._busy_started)
        self.analyze_btn.configure(state="disabled", text=tr("Analyzing") + dots)
        self.title_lbl.configure(text=tr("Analyzing the link") + dots)
        text = tr("Fetching the title, available qualities and subtitles… {secs} s", secs=secs)
        if secs >= 12:
            text += "  — " + tr("taking longer than usual, YouTube is responding slowly")
        self.probe_status.configure(text=text, text_color=theme.INFO)
        self._busy_job = self.after(400, self._busy_tick, n + 1)

    def _pill(self, text: str, ok: bool) -> None:
        ctk.CTkLabel(
            self.pills, text=f" {text} ", corner_radius=9, height=20, font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("white", "white") if ok else ("#fde047", "#fde047"),
            text_color=theme.BRAND_DARK if ok else ("#713f12", "#713f12"),
        ).pack(side="left", padx=2)

    # ======================================================================
    # Mode and options
    # ======================================================================
    def _on_mode_label(self, label: str) -> None:
        mode = next(k for k, v in self.mode_labels.items() if v == label)
        self._apply_mode(mode)

    def _apply_mode(self, mode: str) -> None:
        if mode not in self.mode_labels:
            mode = MODE_VIDEO
        self.mode = mode
        self.mode_seg.set(self.mode_labels[mode])
        color, hover = theme.mode_colors(mode)
        self.mode_seg.configure(selected_color=color, selected_hover_color=hover)
        self.add_btn.configure(fg_color=color, hover_color=hover)
        self.mode_stripe.configure(fg_color=color)
        for cb in (self.compat_cb, self.subs_cb):
            cb.configure(fg_color=color, hover_color=hover)
        if mode == MODE_VIDEO:
            self.audio_frame.grid_forget()
            self.video_frame.grid(row=0, column=1, sticky="w", padx=(4, 10), pady=(12, 4))
            self.subs_frame.pack(side="left", before=self.sb_label)
        else:
            self.video_frame.grid_forget()
            self.audio_frame.grid(row=0, column=1, sticky="w", padx=(4, 10), pady=(12, 4))
            self.subs_frame.pack_forget()
        self._save_opts()

    def _save_opts(self, *_):
        if not hasattr(self, "sb"):
            return  # called while the window is being built
        s = self.settings
        s.mode = self.mode
        s.video_quality = self.vq.get()
        s.container = self.cont_var.get()
        s.compat = bool(self.compat_var.get())
        s.audio_format = self.af.get()
        s.audio_quality = self.aq.get()
        s.subs = bool(self.subs_var.get())
        s.sub_langs = self.langs_var.get().strip()
        s.sponsorblock = self.sb.get()

        self.aq_menu.configure(state="normal" if s.audio_format in LOSSY_AUDIO else "disabled")
        self.langs_entry.configure(state="normal" if s.subs else "disabled")
        self.opts_hint.configure(text="ⓘ  " + self._hint())

    def _hint(self) -> str:
        s = self.settings
        if self.mode == MODE_VIDEO:
            if s.compat:
                base = tr("Best quality among H.264/AAC — plays everywhere (TVs, phones, editors), usually up to 1080p.")
            elif s.container == "MKV":
                base = tr("Highest resolution and FPS (usually AV1/VP9 + Opus) without re-encoding, merged into MKV.")
            else:
                base = tr("Highest resolution and FPS without re-encoding, in MP4 (not every player handles AV1/VP9 in MP4).")
            if s.subs:
                langs = s.sub_langs or "?"
                if not LANGS_RE.match(langs.replace(" ", "")):
                    base += "  ⚠ " + tr("Subtitle languages: comma-separated codes, e.g. pl,en")
                elif s.sub_embed:
                    base += " " + tr("Subtitles {langs} embedded in the file.", langs=langs)
                else:
                    base += " " + tr("Subtitles {langs} as separate .srt files.", langs=langs)
        else:
            fmt = s.audio_format
            if fmt == "best":
                base = tr("The best audio track exactly as it is on YouTube (usually Opus ~130–160 kb/s) — lossless.")
            elif fmt in ("flac", "wav"):
                base = tr("Conversion to a lossless format: a bigger file, but no better than the source.")
            else:
                base = tr("Conversion to {fmt} (re-encoding). Cover art and tags are embedded.", fmt=fmt.upper())
        if s.sponsorblock == SB_REMOVE:
            base += " " + tr("SponsorBlock will cut out: {cats}.", cats=s.sb_categories.replace(",", ", "))
        elif s.sponsorblock == SB_MARK:
            base += " " + tr("SponsorBlock will mark segments as chapters.")
        return base

    def _on_parallel(self, value: str) -> None:
        self.settings.max_parallel = int(value)
        self.dq.set_max_parallel(int(value))

    def _on_appearance(self, _label: str) -> None:
        self.settings.appearance = self.appearance_choice.get()
        ctk.set_appearance_mode(self.settings.appearance)
        self.after(50, self.queue_view.restyle)

    def _on_language(self, _label: str) -> None:
        code = self.lang_choice.get()
        if code == get_language():
            return
        self.settings.language = code
        self.settings.save()
        # Ask in the newly chosen language
        set_language(code)
        question = tr("The language will change after a restart. Restart now?")
        set_language(self.settings.language)
        if messagebox.askyesno(APP_TITLE, question, parent=self):
            self._restart_requested = True
            self._on_close()
        else:
            self.set_status(tr("The language will change after a restart."), theme.WARNING)

    def choose_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self.dir_var.get() or default_out_dir(), title=tr("Target folder"))
        if d:
            self.dir_var.set(str(Path(d)))

    def open_dir(self) -> None:
        d = Path(self.dir_var.get() or default_out_dir())
        d.mkdir(parents=True, exist_ok=True)
        open_path(d)

    def open_settings(self) -> None:
        SettingsDialog(self, self.settings, self._on_settings_saved)

    def _on_settings_saved(self) -> None:
        self.dq.verbose = self.settings.verbose_log
        self._save_opts()
        self.set_status(tr("Settings saved."))

    def set_status(self, text: str, color=None) -> None:
        self.status_lbl.configure(text=text, text_color=color or GRAY)

    # ======================================================================
    # Link analysis
    # ======================================================================
    def _clipboard_url(self) -> str:
        try:
            text = self.clipboard_get().strip()
        except Exception:
            return ""
        return text if URL_RE.match(text) else ""

    def _on_focus_out(self, event) -> None:
        # FocusOut also fires when focus moves between widgets — check a moment later
        # whether focus really left the application.
        self.after(50, self._check_app_focus)

    def _check_app_focus(self) -> None:
        try:
            self._app_has_focus = self.focus_displayof() is not None
        except Exception:
            self._app_has_focus = False

    def _on_focus(self, event) -> None:
        if self._app_has_focus:
            return  # focus change inside the window
        self._app_has_focus = True
        if not self.settings.auto_paste:
            return
        url = self._clipboard_url()
        if url and not self.url_var.get().strip() and url != self._last_auto_paste:
            self._last_auto_paste = url
            self.url_var.set(url)
            self.analyze()

    def paste_and_analyze(self) -> None:
        url = self._clipboard_url()
        if not url:
            self.probe_status.configure(text=tr("The clipboard does not contain a link."), text_color=RED)
            return
        self.url_var.set(url)
        self.analyze()

    def _analyze_if_url(self) -> None:
        if URL_RE.match(self.url_var.get().strip()):
            self.analyze()

    def analyze(self, then_add: bool = False) -> None:
        url = self.url_var.get().strip()
        if not url:
            self.probe_status.configure(text=tr("Type or paste a link."), text_color=RED)
            return
        if not URL_RE.match(url):
            self.probe_status.configure(
                text=tr("This does not look like a link (it should start with https://)."), text_color=RED
            )
            return
        self._add_after_probe = self._add_after_probe or then_add
        if self._probing == url:
            return
        self._probing = url
        self.formats_btn.configure(state="disabled")
        self._set_busy(True, url)
        net = self.settings.net()

        def work():
            try:
                res = probe(url, self.tools, net)
                self.ui_events.put(("probe_ok", url, res))
            except Exception as e:  # noqa: BLE001
                self.ui_events.put(("probe_err", url, short_error(e)))

        threading.Thread(target=work, daemon=True, name="probe").start()

    def _on_probe_ok(self, url: str, res: ProbeResult) -> None:
        if self._probing != url:
            return  # result of an outdated probe
        self._probing = None
        self._set_busy(False)
        self.probe_result, self.probe_input = res, url
        self.title_lbl.configure(text=res.title)
        self.details_lbl.configure(text=res.summary())
        self.formats_btn.configure(state="normal" if res.kind == "video" and res.formats else "disabled")
        if res.kind == "playlist":
            self.probe_status.configure(text="✔ " + tr("Click “Add to list” to choose entries."), text_color=GREEN)
        else:
            self.probe_status.configure(text="✔ " + tr("Ready to add."), text_color=GREEN)
        img = self._blank_thumb
        if res.thumbnail_bytes:
            try:
                pil = Image.open(BytesIO(res.thumbnail_bytes)).convert("RGB")
                pil.thumbnail(THUMB_SIZE)
                img = ctk.CTkImage(pil, size=pil.size)
            except Exception:
                pass
        self._thumb_img = img  # keep a reference so the image is not garbage-collected
        self.thumb_lbl.configure(image=img)
        if self._add_after_probe:
            self._add_after_probe = False
            self.add()

    def _on_probe_err(self, url: str, msg: str) -> None:
        if self._probing != url:
            return
        self._probing = None
        self._add_after_probe = False
        self._set_busy(False)
        self.probe_result, self.probe_input = None, ""
        self.title_lbl.configure(text=tr("Could not read the link"))
        self.details_lbl.configure(text=ellipsize(url, 120))
        hint = ""
        low = msg.lower()
        if "sign in" in low or "age" in low or "cookies" in low or "private" in low:
            hint = "  " + tr("Try setting cookies in Settings.")
        self.probe_status.configure(text="✖ " + msg + hint, text_color=RED)
        self.thumb_lbl.configure(image=self._blank_thumb)
        self.log("error", tr("Analysis: {msg}", msg=msg))

    # ======================================================================
    # Adding to the list
    # ======================================================================
    def _request(self, url: str, title: str, mode: str | None = None, format_override: str = "") -> DownloadRequest:
        out = self.dir_var.get().strip() or default_out_dir()
        s = self.settings
        s.out_dir = out
        return DownloadRequest(
            url=url,
            out_dir=Path(out),
            mode=mode or self.mode,
            video_quality=s.video_quality,
            container=s.container,
            compat=s.compat,
            audio_format=s.audio_format,
            audio_quality=s.audio_quality,
            template=s.template,
            title=title,
            format_override=format_override,
            subs=s.subs,
            sub_langs=s.sub_langs,
            sub_auto=s.sub_auto,
            sub_embed=s.sub_embed,
            sponsorblock=s.sponsorblock,
            sb_categories=s.sb_categories,
            net=s.net(),
        )

    def add(self) -> None:
        url = self.url_var.get().strip()
        res = self.probe_result
        if res is None or self.probe_input != url:
            self.analyze(then_add=True)
            return
        if res.kind == "playlist":
            if not res.entries:
                self.probe_status.configure(text=tr("The playlist is empty."), text_color=RED)
                return
            PlaylistDialog(self, res, self._add_entries)
        else:
            if self._enqueue(self._request(res.url, res.title)):
                self._added_msg(1)

    def _add_entries(self, entries: list[Entry]) -> None:
        added = skipped = 0
        for e in entries:
            req = self._request(e.url, e.title)
            if self.find_duplicate(req) is not None:
                skipped += 1
                continue
            if self._enqueue(req, check_dup=False):
                added += 1
        self._added_msg(added, skipped)

    def open_formats(self) -> None:
        res = self.probe_result
        if res is None or res.kind != "video":
            return
        FormatDialog(self, res, self._add_with_format)

    def _add_with_format(self, spec: str, mode: str) -> None:
        res = self.probe_result
        if res is None:
            return
        if self._enqueue(self._request(res.url, res.title, mode=mode, format_override=spec)):
            self._added_msg(1)

    def _added_msg(self, n: int, skipped: int = 0) -> None:
        skip = (" " + tr("Skipped duplicates: {n}.", n=skipped)) if skipped else ""
        if not n:
            if skipped:
                self.probe_status.configure(
                    text=tr("All entries are already on the list.") + skip, text_color=theme.WARNING
                )
            return
        what = tr("Added to the list") if n == 1 else tr("Added {n} items to the list", n=n)
        if self.settings.autostart:
            text = "✔ " + tr("{what} and started.", what=what) + skip
        else:
            text = "✔ " + tr("{what}. Start it with “▶ Download all”.", what=what) + skip
        self.probe_status.configure(text=text, text_color=GREEN)

    def find_duplicate(self, req: DownloadRequest) -> Task | None:
        key = dup_key(req)
        for task in self.dq.tasks():
            gone = task.state == State.DONE and task.result_path and not task.result_path.exists()
            if dup_key(task.request) == key and not gone:
                return task
        return None

    def _enqueue(self, req: DownloadRequest, check_dup: bool = True) -> bool:
        try:
            cmd = command_line(req, self.tools)  # validate options before adding
        except ValueError as e:
            self.probe_status.configure(text=str(e), text_color=RED)
            return False
        if check_dup:
            dup = self.find_duplicate(req)
            if dup is not None:
                title = ellipsize(req.title or req.url, 80)
                if dup.state == State.DONE:
                    why = tr("“{title}” in the same mode was already downloaded as #{id}:\n{path}",
                             title=title, id=dup.id, path=dup.result_path)
                else:
                    why = tr("“{title}” in the same mode is already on the list as #{id} ({state}).",
                             title=title, id=dup.id, state=dup.state.label)
                question = why + "\n\n" + tr(
                    "A second task would be saved under the same file name, so yt-dlp would skip it. "
                    "Change the mode/format or add it anyway.\n\nAdd anyway?"
                )
                if not messagebox.askyesno(APP_TITLE, question, parent=self):
                    self.probe_status.configure(text=tr("Not added — duplicate."), text_color=theme.WARNING)
                    return False
        task = self.dq.add(req, start=self.settings.autostart)
        self.log("debug" if not self.settings.verbose_log else "info", f"[#{task.id}] {cmd}")
        return True

    # ======================================================================
    # yt-dlp update
    # ======================================================================
    def update_ytdlp(self) -> None:
        if getattr(sys, "frozen", False):
            messagebox.showinfo(
                APP_TITLE, tr("In the packaged app yt-dlp is built in — updating it requires a new release of the app."),
            )
            return
        if self._updating:
            return
        if self.dq.active_count:
            messagebox.showwarning(APP_TITLE, tr("Finish or cancel the running downloads first."))
            return
        if not messagebox.askyesno(
            APP_TITLE, tr("Update yt-dlp (currently {version}) and deno with pip?", version=yt_dlp.version.__version__)
        ):
            return
        self._updating = True
        self.update_btn.configure(state="disabled", text="⌛ " + tr("Updating…"))
        if not self._log_visible:
            self.toggle_log()
        exe = Path(sys.executable)
        py = exe.with_name("python.exe") if exe.name.lower() == "pythonw.exe" else exe
        old = yt_dlp.version.__version__

        def work():
            cmd = [str(py), "-m", "pip", "install", "-U", "--disable-pip-version-check",
                   "yt-dlp[default,curl-cffi]", "deno"]
            self.ui_events.put(("log", "info", "> " + subprocess.list2cmdline(cmd)))
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        self.ui_events.put(("log", "debug", line))
                rc = proc.wait()
                new = subprocess.run(
                    [str(py), "-c", "import yt_dlp.version as v; print(v.__version__)"],
                    capture_output=True, text=True, creationflags=NO_WINDOW,
                ).stdout.strip()
                self.ui_events.put(("update_done", rc, old, new))
            except Exception as e:  # noqa: BLE001
                self.ui_events.put(("update_done", -1, old, str(e)))

        threading.Thread(target=work, daemon=True, name="update").start()

    def _on_update_done(self, rc: int, old: str, new: str) -> None:
        self._updating = False
        self.update_btn.configure(state="normal", text="⟳ yt-dlp")
        if rc != 0:
            self.log("error", tr("The update failed (code {rc}): {detail}", rc=rc, detail=new))
            messagebox.showerror(APP_TITLE, tr("The update failed — see the log for details."))
        elif new and new != old:
            self.log("info", tr("yt-dlp updated: {old} → {new}", old=old, new=new))
            self.set_status(tr("yt-dlp {new} installed — restart the app.", new=new), theme.WARNING)
            messagebox.showinfo(
                APP_TITLE, tr("yt-dlp updated: {old} → {new}", old=old, new=new) + "\n" + tr("Restart the app.")
            )
        else:
            self.log("info", tr("yt-dlp is up to date ({version}).", version=old))
            messagebox.showinfo(APP_TITLE, tr("You have the latest yt-dlp ({version}).", version=old))

    # ======================================================================
    # Event loop for worker threads
    # ======================================================================
    def _poll(self) -> None:
        try:
            while True:
                kind, *args = self.ui_events.get_nowait()
                if kind == "probe_ok":
                    self._on_probe_ok(*args)
                elif kind == "probe_err":
                    self._on_probe_err(*args)
                elif kind == "log":
                    self.log(*args)
                elif kind == "update_done":
                    self._on_update_done(*args)
        except queue.Empty:
            pass

        dirty: set[int] = set()
        structural = False
        try:
            for _ in range(5000):
                ev = self.dq.events.get_nowait()
                if ev.kind == "added":
                    self.queue_view.add_task(ev.data)
                    structural = True
                elif ev.kind == "removed":
                    dirty.discard(ev.task_id)
                    self.queue_view.remove_task(ev.task_id)
                    structural = True
                elif ev.kind == "log":
                    level, msg = ev.data
                    self.log(level, f"[#{ev.task_id}] {msg}")
                else:
                    dirty.add(ev.task_id)
                    if ev.kind == "state":
                        structural = True
                        self._log_state(ev.task_id)
        except queue.Empty:
            pass
        for tid in dirty:
            self.queue_view.refresh_task(tid)
        if structural:
            self.queue_view.on_state_change()
            self._queue_dirty = True
        if self._queue_dirty and self.settings.restore_queue:
            self._queue_dirty = False
            self.dq.save(queue_file())
        self._update_activity()
        self._poll_id = self.after(100, self._poll)

    def _update_activity(self) -> None:
        """Combined speed in the status bar + notification when the list finishes."""
        active = self.dq.active_count
        now = time.monotonic()
        if active and now - self._speed_shown_at >= 1.0:
            self._speed_shown_at = now
            speed = self.dq.total_speed()
            running = self.dq.counts()[State.RUNNING]
            txt = "⬇ " + tr("in progress {running}/{active}", running=running, active=active)
            if speed:
                txt += f"  ·  {human_speed(speed)}"
            self.speed_lbl.configure(text=txt)
        elif not active and self.speed_lbl.cget("text"):
            self.speed_lbl.configure(text="")
        if self._was_active and not active:
            c = self.dq.counts()
            summary = tr("List finished — done: {done}", done=c[State.DONE])
            if c[State.ERROR]:
                summary += ", " + tr("errors: {n}", n=c[State.ERROR])
            self.set_status(("✔ " if not c[State.ERROR] else "⚠ ") + summary, GREEN if not c[State.ERROR] else RED)
            if self.settings.notify_done:
                notify_done(self)
        self._was_active = bool(active)

    # ======================================================================
    # Keyboard shortcuts and clipboard watching
    # ======================================================================
    def _bind_shortcuts(self) -> None:
        def focus_url(_e=None):
            self.url_entry.focus_set()
            self.url_entry.select_range(0, "end")
            return "break"

        self.bind("<Control-l>", focus_url)
        self.bind("<F5>", lambda e: self.analyze())
        self.bind("<Control-Return>", lambda e: (self.add(), "break")[1])
        self.bind("<Control-d>", lambda e: (self.queue_view.start_all(), "break")[1])
        self.bind("<Control-comma>", lambda e: self.open_settings())

    def _watch_clipboard(self) -> None:
        if self.settings.watch_clipboard:
            try:
                text = self.clipboard_get().strip()
            except Exception:
                text = ""
            if text and text != self._clip_seen:
                self._clip_seen = text
                if is_youtube_url(text) and text != self.url_var.get().strip():
                    self.url_var.set(text)
                    self.log("info", tr("Clipboard: {text}", text=text))
                    self.analyze(then_add=True)
        self._clip_job = self.after(1000, self._watch_clipboard)

    def _log_state(self, tid: int) -> None:
        task = self.dq.get(tid)
        if task is None or not task.state.finished:
            return
        extra = f": {task.result_path}" if task.result_path else (f": {task.error}" if task.error else "")
        self.log("error" if task.error else "info", f"[#{tid}] {task.state.label}{extra}")
        if task.state == State.DONE:
            self.set_status("✔ " + tr("Downloaded: {title}", title=ellipsize(task.request.title, 90)), GREEN)
        elif task.state == State.ERROR:
            self.set_status(
                "✖ " + tr("Error: {title} — {error}", title=ellipsize(task.request.title, 60),
                          error=ellipsize(task.error, 80)),
                RED,
            )

    # ======================================================================
    # Log and tools
    # ======================================================================
    def toggle_log(self) -> None:
        self._log_visible = not self._log_visible
        if self._log_visible:
            self.log_box.grid(row=7, column=0, sticky="nsew", padx=14, pady=(0, 12))
            self.log_btn.configure(text="▾ Log")
        else:
            self.log_box.grid_forget()
            self.log_btn.configure(text="▸ Log")

    def log(self, level: str, msg: str) -> None:
        box = self.log_box
        box.configure(state="normal")
        box.insert("end", msg + "\n", level if level in ("error", "warning", "debug") else None)
        lines = int(box.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            box.delete("1.0", f"{lines - MAX_LOG_LINES}.0")
        box.see("end")
        box.configure(state="disabled")

    def _report_tools(self) -> None:
        tools = self.tools
        self._pill(f"yt-dlp {yt_dlp.version.__version__}", True)
        for name in ("ffmpeg", "deno"):
            ok = getattr(tools, name) is not None
            self._pill(f"{name} {'✓' if ok else '✗'}", ok)
        if not tools.ok:
            miss = ", ".join(tools.missing)
            self.set_status("⚠ " + tr("Missing: {tools} — run the setup_env script", tools=miss), RED)
            self.log(
                "warning",
                tr("Not found: {tools}. Without deno YouTube only offers low qualities; without ffmpeg "
                   "nothing can be merged or converted.", tools=miss),
            )
        for name in ("ffmpeg", "ffprobe", "deno"):
            self.log("debug", f"{name}: {getattr(tools, name)}")

    # ======================================================================
    # Closing
    # ======================================================================
    def _on_close(self) -> None:
        running = self.dq.active_count
        if running and not messagebox.askyesno(
            APP_TITLE,
            tr("Downloading in progress ({n}). Close and stop it?\n"
               "Unfinished tasks will return to the list on the next start.", n=running),
        ):
            self._restart_requested = False
            return
        if self.settings.restore_queue:
            self.dq.save(queue_file())
        else:
            try:
                os.remove(queue_file())
            except OSError:
                pass
        self.dq.cancel_all()
        self.settings.out_dir = self.dir_var.get().strip() or default_out_dir()
        if self.state() == "normal":
            self.settings.geometry = self.geometry()
        self.settings.save()
        try:
            self.after_cancel(self._poll_id)
            self.after_cancel(self._clip_job)
        except Exception:
            pass
        self.destroy()
        if self._restart_requested:
            try:
                subprocess.Popen(restart_command(), cwd=str(Path(__file__).resolve().parents[2]))
            except OSError:
                pass


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
