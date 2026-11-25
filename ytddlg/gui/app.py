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
    SPONSORBLOCK,
    VIDEO_QUALITIES,
    DownloadRequest,
    command_line,
)
from ..core.probe import Entry, ProbeResult, probe
from ..core.queue import DownloadQueue, State, Task, short_error
from ..core.tools import detect_tools
from . import theme
from .dialogs import FormatDialog, PlaylistDialog, SettingsDialog
from .fmt import ellipsize, human_speed
from .notify import is_youtube_url, notify_done
from .queue_view import QueueView, open_path
from .resources import load_logo, set_window_icon

MODE_LABELS = {MODE_VIDEO: "▶ Wideo", MODE_AUDIO: "♫ Tylko audio"}
APPEARANCE = {"System": "System", "Ciemny": "Dark", "Jasny": "Light"}
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


class App(ctk.CTk):
    def __init__(self, settings: Settings | None = None, restore: bool = True) -> None:
        self.settings = settings or Settings.load()
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

        self._build()
        self._apply_mode(self.settings.mode)
        self._report_tools()

        if restore and self.settings.restore_queue:
            n = self.dq.load(queue_file())
            if n:
                self.log("info", f"Przywrócono {n} niezakończonych zadań z poprzedniej sesji.")

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
            header, text="⚙ Ustawienia", width=96, height=26, corner_radius=7, command=self.open_settings, **ON_BRAND
        ).grid(row=0, column=4, padx=(0, 5))
        self.update_btn = ctk.CTkButton(
            header, text="⟳ yt-dlp", width=74, height=26, corner_radius=7, command=self.update_ytdlp, **ON_BRAND
        )
        self.update_btn.grid(row=0, column=5, padx=(0, 5))
        inv = {v: k for k, v in APPEARANCE.items()}
        self.app_var = ctk.StringVar(value=inv.get(self.settings.appearance, "System"))
        ctk.CTkOptionMenu(
            header, values=list(APPEARANCE), variable=self.app_var, width=88, height=26, corner_radius=7,
            command=self._on_appearance, fg_color="white", button_color=theme.ON_BRAND_SOFT,
            button_hover_color=theme.ON_BRAND_HOVER, text_color=theme.BRAND_DARK,
            dropdown_fg_color=theme.CARD, dropdown_text_color=theme.TEXT,
        ).grid(row=0, column=6, padx=(0, 12))

        # --- URL -----------------------------------------------------------
        url_row = ctk.CTkFrame(self, fg_color="transparent")
        url_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(12, 4))
        url_row.grid_columnconfigure(0, weight=1)
        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(
            url_row, textvariable=self.url_var, height=38, corner_radius=10, border_width=2,
            border_color=theme.CARD_BORDER, fg_color=theme.CARD, font=ctk.CTkFont(size=14),
            placeholder_text="Wklej link do filmu, playlisty albo kanału YouTube…",
        )
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.url_entry.bind("<Return>", lambda e: self.analyze())
        self.url_entry.bind("<<Paste>>", lambda e: self.after(50, self._analyze_if_url))
        self.url_entry.bind("<FocusIn>", lambda e: self.url_entry.configure(border_color=theme.INFO), add="+")
        self.url_entry.bind("<FocusOut>", lambda e: self.url_entry.configure(border_color=theme.CARD_BORDER), add="+")
        ctk.CTkButton(
            url_row, text="Wklej", width=90, height=38, corner_radius=10, command=self.paste_and_analyze, **FLAT
        ).grid(row=0, column=1, padx=(8, 0))
        self.analyze_btn = ctk.CTkButton(
            url_row, text="Analizuj", width=110, height=38, corner_radius=10, command=self.analyze,
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
            info, text="Brak analizowanego linku", anchor="w", justify="left",
            font=ctk.CTkFont(size=16, weight="bold"), wraplength=600,
        )
        self.title_lbl.grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=(12, 0))
        self.details_lbl = ctk.CTkLabel(info, text="", anchor="w", justify="left", text_color=GRAY, wraplength=600)
        self.details_lbl.grid(row=1, column=2, sticky="ew", padx=(0, 10))
        self.probe_status = ctk.CTkLabel(info, text="", anchor="w", justify="left", wraplength=600)
        self.probe_status.grid(row=2, column=2, sticky="new", padx=(0, 10), pady=(0, 10))
        self.formats_btn = ctk.CTkButton(
            info, text="☰ Formaty…", width=104, height=32, state="disabled", command=self.open_formats, **FLAT
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
            opts, values=list(MODE_LABELS.values()), command=self._on_mode_label, height=34,
            font=ctk.CTkFont(size=13, weight="bold"), unselected_color=theme.FLAT_BTN,
            unselected_hover_color=theme.FLAT_HOVER, fg_color=theme.FLAT_BTN, text_color=theme.TEXT,
        )
        self.mode_seg.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        menu_kw = {"fg_color": theme.FLAT_BTN, "button_color": theme.FLAT_HOVER,
                   "button_hover_color": theme.FLAT_HOVER, "text_color": theme.TEXT}
        # Video options
        self.video_frame = ctk.CTkFrame(opts, fg_color="transparent")
        ctk.CTkLabel(self.video_frame, text="Jakość:").pack(side="left", padx=(4, 4))
        self.vq_var = ctk.StringVar(value=self._valid(self.settings.video_quality, VIDEO_QUALITIES, "Najlepsza"))
        ctk.CTkOptionMenu(
            self.video_frame, values=list(VIDEO_QUALITIES), variable=self.vq_var, width=124,
            command=self._save_opts, **menu_kw,
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(self.video_frame, text="Kontener:").pack(side="left", padx=(0, 4))
        self.cont_var = ctk.StringVar(value=self._valid(self.settings.container, CONTAINERS, "MKV"))
        ctk.CTkOptionMenu(
            self.video_frame, values=CONTAINERS, variable=self.cont_var, width=76, command=self._save_opts, **menu_kw
        ).pack(side="left", padx=(0, 12))
        self.compat_var = ctk.BooleanVar(value=self.settings.compat)
        self.compat_cb = ctk.CTkCheckBox(
            self.video_frame, text="Zgodność (H.264/AAC)", variable=self.compat_var, command=self._save_opts
        )
        self.compat_cb.pack(side="left")

        # Audio options
        self.audio_frame = ctk.CTkFrame(opts, fg_color="transparent")
        ctk.CTkLabel(self.audio_frame, text="Format:").pack(side="left", padx=(4, 4))
        self.af_var = ctk.StringVar(
            value=self._valid(self.settings.audio_format, AUDIO_FORMATS, "Oryginał (bez rekompresji)")
        )
        ctk.CTkOptionMenu(
            self.audio_frame, values=list(AUDIO_FORMATS), variable=self.af_var, width=220,
            command=self._save_opts, **menu_kw,
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(self.audio_frame, text="Jakość:").pack(side="left", padx=(0, 4))
        self.aq_var = ctk.StringVar(value=self._valid(self.settings.audio_quality, AUDIO_QUALITIES, "Najlepsza (VBR)"))
        self.aq_menu = ctk.CTkOptionMenu(
            self.audio_frame, values=list(AUDIO_QUALITIES), variable=self.aq_var, width=150,
            command=self._save_opts, **menu_kw,
        )
        self.aq_menu.pack(side="left")

        # Extras: subtitles + SponsorBlock
        extras = ctk.CTkFrame(opts, fg_color="transparent")
        extras.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 0))
        self.subs_frame = ctk.CTkFrame(extras, fg_color="transparent")
        self.subs_var = ctk.BooleanVar(value=self.settings.subs)
        self.subs_cb = ctk.CTkCheckBox(
            self.subs_frame, text="Napisy:", variable=self.subs_var, command=self._save_opts, width=80
        )
        self.subs_cb.pack(side="left")
        self.langs_var = ctk.StringVar(value=self.settings.sub_langs)
        self.langs_var.trace_add("write", lambda *a: self._save_opts())
        self.langs_entry = ctk.CTkEntry(self.subs_frame, textvariable=self.langs_var, width=90, height=28)
        self.langs_entry.pack(side="left", padx=(4, 18))
        self.subs_frame.pack(side="left")
        self.sb_label = ctk.CTkLabel(extras, text="⏭ SponsorBlock:")
        self.sb_label.pack(side="left", padx=(0, 4))
        inv_sb = {v: k for k, v in SPONSORBLOCK.items()}
        self.sb_var = ctk.StringVar(value=inv_sb.get(self.settings.sponsorblock, "Wyłączony"))
        ctk.CTkOptionMenu(
            extras, values=list(SPONSORBLOCK), variable=self.sb_var, width=190, command=self._save_opts, **menu_kw
        ).pack(side="left")

        self.opts_hint = ctk.CTkLabel(opts, text="", anchor="w", justify="left", text_color=GRAY, wraplength=900)
        self.opts_hint.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(6, 4))

        # Folder + add button (same card)
        folder = ctk.CTkFrame(opts, fg_color="transparent")
        folder.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(2, 12))
        folder.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(folder, text="Folder:").grid(row=0, column=0, padx=(2, 8))
        self.dir_var = ctk.StringVar(value=self.settings.out_dir)
        ctk.CTkEntry(folder, textvariable=self.dir_var, height=32).grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(folder, text="Wybierz…", width=86, height=32, command=self.choose_dir, **FLAT).grid(
            row=0, column=2, padx=(8, 0)
        )
        ctk.CTkButton(folder, text="Otwórz", width=74, height=32, command=self.open_dir, **FLAT).grid(
            row=0, column=3, padx=(8, 0)
        )
        self.add_btn = ctk.CTkButton(
            folder, text="＋ Dodaj do listy", width=170, height=34, corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"), command=self.add,
        )
        self.add_btn.grid(row=0, column=4, padx=(14, 0))

        # --- Queue -----------------------------------------------------------
        self.queue_view = QueueView(self, self.dq, on_parallel=self._on_parallel, parallel=self.settings.max_parallel)
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
            bottom, text="Ctrl+L link · F5 analizuj · Ctrl+Enter dodaj · Ctrl+D pobierz",
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

    @staticmethod
    def _valid(value, allowed, default):
        return value if value in allowed else default

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
            self.set_status("⌛ Analizuję link…", theme.INFO)
            self._busy_tick(0)
        else:
            self.probe_bar.stop()
            self.probe_bar.grid_remove()
            self.info_card.configure(border_color=theme.CARD_BORDER, border_width=1)
            self.url_entry.configure(border_color=theme.CARD_BORDER)
            self.title_lbl.configure(text_color=theme.TEXT)
            self.analyze_btn.configure(state="normal", text="Analizuj")
            self.set_status("")

    def _busy_tick(self, n: int) -> None:
        dots = "." * (n % 4)
        secs = int(time.monotonic() - self._busy_started)
        self.analyze_btn.configure(state="disabled", text=f"Analizuję{dots}")
        self.title_lbl.configure(text=f"Analizuję link{dots}")
        extra = "  — dłużej niż zwykle, YouTube odpowiada wolno" if secs >= 12 else ""
        self.probe_status.configure(
            text=f"Pobieram tytuł, dostępne jakości i napisy… {secs} s{extra}", text_color=theme.INFO
        )
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
        mode = next(k for k, v in MODE_LABELS.items() if v == label)
        self._apply_mode(mode)

    def _apply_mode(self, mode: str) -> None:
        if mode not in MODE_LABELS:
            mode = MODE_VIDEO
        self.mode = mode
        self.mode_seg.set(MODE_LABELS[mode])
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
        if not hasattr(self, "sb_var"):
            return  # called while the window is being built
        s = self.settings
        s.mode = self.mode
        s.video_quality = self.vq_var.get()
        s.container = self.cont_var.get()
        s.compat = bool(self.compat_var.get())
        s.audio_format = self.af_var.get()
        s.audio_quality = self.aq_var.get()
        s.subs = bool(self.subs_var.get())
        s.sub_langs = self.langs_var.get().strip()
        s.sponsorblock = SPONSORBLOCK.get(self.sb_var.get(), "off")

        fmt = AUDIO_FORMATS.get(s.audio_format, "best")
        self.aq_menu.configure(state="normal" if fmt in LOSSY_AUDIO else "disabled")
        self.langs_entry.configure(state="normal" if s.subs else "disabled")
        self.opts_hint.configure(text="ⓘ  " + self._hint())

    def _hint(self) -> str:
        s = self.settings
        if self.mode == MODE_VIDEO:
            if self.compat_var.get():
                base = "Najlepsza jakość wśród H.264/AAC — działa wszędzie (TV, telefony, edytory), zwykle do 1080p."
            elif self.cont_var.get() == "MKV":
                base = "Najwyższa rozdzielczość i FPS (zwykle AV1/VP9 + Opus) bez rekompresji, scalone do MKV."
            else:
                base = "Najwyższa rozdzielczość i FPS bez rekompresji, w MP4 (AV1/VP9 w MP4 nie każdy odtwarzacz obsłuży)."
            if s.subs:
                langs = s.sub_langs or "?"
                if not LANGS_RE.match(langs.replace(" ", "")):
                    base += "  ⚠ Języki napisów: kody rozdzielone przecinkami, np. pl,en"
                else:
                    how = "osadzone w pliku" if s.sub_embed else "jako osobne .srt"
                    base += f" Napisy {langs} {how}."
        else:
            fmt = AUDIO_FORMATS.get(self.af_var.get(), "best")
            if fmt == "best":
                base = "Najlepsza ścieżka audio dokładnie tak, jak jest na YouTube (zwykle Opus ~130–160 kb/s) — bez strat."
            elif fmt in ("flac", "wav"):
                base = "Konwersja do formatu bezstratnego: większy plik, ale jakość nie wyższa niż źródło."
            else:
                base = f"Konwersja do {fmt.upper()} (rekompresja). Okładka i tagi są osadzane w pliku."
        if s.sponsorblock == "remove":
            base += " SponsorBlock wytnie: " + s.sb_categories.replace(",", ", ") + "."
        elif s.sponsorblock == "mark":
            base += " SponsorBlock oznaczy segmenty jako rozdziały."
        return base

    def _on_parallel(self, value: str) -> None:
        self.settings.max_parallel = int(value)
        self.dq.set_max_parallel(int(value))

    def _on_appearance(self, label: str) -> None:
        self.settings.appearance = APPEARANCE[label]
        ctk.set_appearance_mode(self.settings.appearance)
        self.after(50, self.queue_view.restyle)

    def choose_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self.dir_var.get() or default_out_dir(), title="Folder docelowy")
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
        self.set_status("Zapisano ustawienia.")

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
            self.probe_status.configure(text="Schowek nie zawiera linku.", text_color=RED)
            return
        self.url_var.set(url)
        self.analyze()

    def _analyze_if_url(self) -> None:
        if URL_RE.match(self.url_var.get().strip()):
            self.analyze()

    def analyze(self, then_add: bool = False) -> None:
        url = self.url_var.get().strip()
        if not url:
            self.probe_status.configure(text="Wpisz lub wklej link.", text_color=RED)
            return
        if not URL_RE.match(url):
            self.probe_status.configure(text="To nie wygląda na link (powinien zaczynać się od https://).", text_color=RED)
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
            self.probe_status.configure(text="✔ Kliknij „Dodaj do listy”, aby wybrać pozycje.", text_color=GREEN)
        else:
            self.probe_status.configure(text="✔ Gotowe do dodania.", text_color=GREEN)
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
        self.title_lbl.configure(text="Nie udało się odczytać linku")
        self.details_lbl.configure(text=ellipsize(url, 120))
        hint = ""
        low = msg.lower()
        if "sign in" in low or "age" in low or "cookies" in low or "private" in low:
            hint = "  Spróbuj ustawić cookies w Ustawieniach."
        self.probe_status.configure(text="✖ " + msg + hint, text_color=RED)
        self.thumb_lbl.configure(image=self._blank_thumb)
        self.log("error", f"Analiza: {msg}")

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
            video_quality=self.vq_var.get(),
            container=self.cont_var.get(),
            compat=bool(self.compat_var.get()),
            audio_format=self.af_var.get(),
            audio_quality=self.aq_var.get(),
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
                self.probe_status.configure(text="Playlista jest pusta.", text_color=RED)
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
        skip = f" Pominięto duplikaty: {skipped}." if skipped else ""
        if not n:
            if skipped:
                self.probe_status.configure(text=f"Wszystkie pozycje są już na liście.{skip}", text_color=theme.WARNING)
            return
        what = "✔ Dodano do listy" if n == 1 else f"✔ Dodano {n} pozycji do listy"
        if self.settings.autostart:
            self.probe_status.configure(text=f"{what} i uruchomiono.{skip}", text_color=GREEN)
        else:
            self.probe_status.configure(
                text=f"{what}. Uruchom przyciskiem „▶ Pobierz wszystkie”.{skip}", text_color=GREEN
            )

    def find_duplicate(self, req: DownloadRequest) -> Task | None:
        key = dup_key(req)
        for t in self.dq.tasks():
            if dup_key(t.request) == key and not (t.state == State.DONE and t.result_path and not t.result_path.exists()):
                return t
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
                if dup.state == State.DONE:
                    why = f"został już pobrany jako #{dup.id}:\n{dup.result_path}"
                else:
                    why = f"jest już na liście jako #{dup.id} ({dup.state.value})."
                if not messagebox.askyesno(
                    APP_TITLE,
                    f"„{ellipsize(req.title or req.url, 80)}” w tym samym trybie {why}\n\n"
                    "Drugie zadanie zapisze się pod tą samą nazwą pliku, więc yt-dlp je pominie. "
                    "Zmień tryb/format albo dodaj mimo to.\n\nDodać mimo to?",
                    parent=self,
                ):
                    self.probe_status.configure(text="Nie dodano — duplikat.", text_color=theme.WARNING)
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
                APP_TITLE, "W wersji spakowanej yt-dlp jest wbudowany — aktualizacja wymaga nowej wersji aplikacji\n"
                "(build_exe.ps1 po aktualizacji yt-dlp w .venv).",
            )
            return
        if self._updating:
            return
        if self.dq.active_count:
            messagebox.showwarning(APP_TITLE, "Najpierw zakończ albo anuluj trwające pobierania.")
            return
        if not messagebox.askyesno(
            APP_TITLE, f"Zaktualizować yt-dlp (obecnie {yt_dlp.version.__version__}) i deno przez pip?"
        ):
            return
        self._updating = True
        self.update_btn.configure(state="disabled", text="⌛ Aktualizuję…")
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
        self.update_btn.configure(state="normal", text="⟳ Aktualizuj yt-dlp")
        if rc != 0:
            self.log("error", f"Aktualizacja nie powiodła się (kod {rc}): {new}")
            messagebox.showerror(APP_TITLE, "Aktualizacja nie powiodła się — szczegóły w logu.")
        elif new and new != old:
            self.log("info", f"yt-dlp zaktualizowany: {old} → {new}")
            self.set_status(f"yt-dlp {new} zainstalowany — uruchom aplikację ponownie.", theme.WARNING)
            messagebox.showinfo(APP_TITLE, f"yt-dlp zaktualizowany: {old} → {new}.\nUruchom aplikację ponownie.")
        else:
            self.log("info", f"yt-dlp jest aktualny ({old}).")
            messagebox.showinfo(APP_TITLE, f"Masz najnowszą wersję yt-dlp ({old}).")

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
            txt = f"⬇ w toku {running}/{active}"
            if speed:
                txt += f"  ·  {human_speed(speed)}"
            self.speed_lbl.configure(text=txt)
        elif not active and self.speed_lbl.cget("text"):
            self.speed_lbl.configure(text="")
        if self._was_active and not active:
            c = self.dq.counts()
            summary = f"Lista zakończona — gotowe: {c[State.DONE]}"
            if c[State.ERROR]:
                summary += f", błędy: {c[State.ERROR]}"
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
                    self.log("info", f"Schowek: {text}")
                    self.analyze(then_add=True)
        self._clip_job = self.after(1000, self._watch_clipboard)

    def _log_state(self, tid: int) -> None:
        t = self.dq.get(tid)
        if t is None or not t.state.finished:
            return
        extra = f": {t.result_path}" if t.result_path else (f": {t.error}" if t.error else "")
        self.log("error" if t.error else "info", f"[#{tid}] {t.state.value}{extra}")
        if t.state == State.DONE:
            self.set_status(f"✔ Pobrano: {ellipsize(t.request.title, 90)}", GREEN)
        elif t.state == State.ERROR:
            self.set_status(f"✖ Błąd: {ellipsize(t.request.title, 60)} — {ellipsize(t.error, 80)}", RED)

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
        t = self.tools
        self._pill(f"yt-dlp {yt_dlp.version.__version__}", True)
        for name in ("ffmpeg", "deno"):
            ok = getattr(t, name) is not None
            self._pill(f"{name} {'✓' if ok else '✗'}", ok)
        if not t.ok:
            miss = ", ".join(t.missing)
            self.set_status(f"⚠ Brakuje: {miss} — uruchom setup_env.ps1", RED)
            self.log(
                "warning",
                f"Nie znaleziono: {miss}. Bez deno YouTube daje tylko niskie jakości, bez ffmpeg nie da się scalać ani konwertować.",
            )
        for name in ("ffmpeg", "ffprobe", "deno"):
            self.log("debug", f"{name}: {getattr(t, name)}")

    # ======================================================================
    # Closing
    # ======================================================================
    def _on_close(self) -> None:
        running = self.dq.active_count
        if running and not messagebox.askyesno(
            APP_TITLE,
            f"Trwa pobieranie ({running}). Zamknąć i przerwać?\n"
            "Niezakończone zadania wrócą na listę przy następnym uruchomieniu.",
        ):
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


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
