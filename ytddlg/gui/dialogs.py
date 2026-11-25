"""Dialogs: playlist entry picker, manual format picker, settings."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from ..config import Settings
from ..core.options import (
    COOKIE_BROWSERS,
    DEFAULT_TEMPLATE,
    MODE_AUDIO,
    MODE_VIDEO,
    RATE_RE,
    SB_ALL_CATEGORIES,
    SB_DEFAULT_CATEGORIES,
)
from ..core.probe import Entry, FormatInfo, ProbeResult, format_duration
from . import theme
from .fmt import human_bytes
from .resources import set_window_icon
from .tree import Column, Table

GRAY = theme.MUTED
RED = theme.RED_TEXT
GREEN = theme.GREEN_TEXT
FLAT = theme.FLAT
CHECK_ON, CHECK_OFF = "☑", "☐"

SB_LABELS = {
    "sponsor": "Sponsor / reklama",
    "selfpromo": "Autopromocja",
    "interaction": "Prośby o subskrypcję",
    "intro": "Intro",
    "outro": "Outro / napisy końcowe",
    "preview": "Zapowiedź / podsumowanie",
    "filler": "Dygresje",
    "music_offtopic": "Muzyka: fragmenty niemuzyczne",
    "hook": "Zajawka (hook)",
}


class Modal(ctk.CTkToplevel):
    def __init__(self, master, title: str, size: tuple[int, int]):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        w, h = size
        master.update_idletasks()
        x = master.winfo_rootx() + max(0, (master.winfo_width() - w) // 2)
        y = master.winfo_rooty() + max(0, (master.winfo_height() - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(w, 520), min(h, 360))
        self.transient(master)
        self.configure(fg_color=theme.WINDOW)
        set_window_icon(self)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda e: self.close())
        self.after(30, self._show)

    def _show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        # CTkToplevel on Windows sets its icon with a delay — grab only once the window is visible
        self.after(150, self._grab)

    def _grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


# =============================================================================
# Playlist
# =============================================================================
class PlaylistDialog(Modal):
    """Entry list with checkboxes. Click = toggle, Shift+click = range."""

    def __init__(self, master, result: ProbeResult, on_ok: Callable[[list[Entry]], None]):
        super().__init__(master, "Wybierz pozycje z playlisty", (760, 620))
        self.result = result
        self.on_ok = on_ok
        self.checked: set[int] = {e.index for e in result.entries}
        self._last_clicked: int | None = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self, text=result.title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w", wraplength=700
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=14, pady=6)
        top.grid_columnconfigure(0, weight=1)
        self.filter_var = ctk.StringVar()
        self.filter_var.trace_add("write", lambda *a: self._fill())
        ctk.CTkEntry(top, textvariable=self.filter_var, placeholder_text="Filtruj po tytule…", height=30).grid(
            row=0, column=0, sticky="ew"
        )
        for i, (txt, fn) in enumerate((("Wszystkie", self._all), ("Żadne", self._none), ("Odwróć", self._invert))):
            ctk.CTkButton(top, text=txt, width=86, height=30, command=fn, **FLAT).grid(row=0, column=i + 1, padx=(6, 0))

        cols = [
            Column("chk", "", 34, "center"),
            Column("idx", "#", 46, "e"),
            Column("title", "Tytuł", 520, "w", stretch=True),
            Column("dur", "Czas", 70, "e"),
        ]
        self.table = Table(self, cols, selectmode="none", height=16)
        self.table.grid(row=2, column=0, sticky="nsew", padx=14)
        self.tree = self.table.tree
        self.tree.bind("<Button-1>", self._on_click)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=14, pady=12)
        bottom.grid_columnconfigure(0, weight=1)
        self.count_lbl = ctk.CTkLabel(bottom, text="", anchor="w", text_color=GRAY)
        self.count_lbl.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(bottom, text="Anuluj", width=90, command=self.close, **FLAT).grid(row=0, column=1, padx=(6, 0))
        self.ok_btn = ctk.CTkButton(bottom, text="Dodaj zaznaczone", width=170, command=self._ok)
        self.ok_btn.grid(row=0, column=2, padx=(6, 0))
        ctk.CTkLabel(
            self, text="Klik zaznacza/odznacza, Shift+klik — cały zakres.", text_color=GRAY, anchor="w"
        ).grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 8))
        self._fill()

    def _visible(self) -> list[Entry]:
        q = self.filter_var.get().strip().lower()
        return [e for e in self.result.entries if not q or q in e.title.lower()]

    def _fill(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for e in self._visible():
            self.tree.insert(
                "",
                "end",
                iid=str(e.index),
                values=(CHECK_ON if e.index in self.checked else CHECK_OFF, e.index, e.title, format_duration(e.duration)),
            )
        self._update_count()

    def _set(self, idx: int, on: bool) -> None:
        (self.checked.add if on else self.checked.discard)(idx)
        if self.tree.exists(str(idx)):
            self.tree.set(str(idx), "chk", CHECK_ON if on else CHECK_OFF)

    def _on_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or self.tree.identify_region(event.x, event.y) not in ("cell", "tree"):
            return None
        idx = int(iid)
        new = idx not in self.checked
        if event.state & 0x0001 and self._last_clicked is not None:  # Shift
            visible = [str(e.index) for e in self._visible()]
            if str(self._last_clicked) in visible:
                a, b = sorted((visible.index(str(self._last_clicked)), visible.index(iid)))
                for v in visible[a : b + 1]:
                    self._set(int(v), new)
        else:
            self._set(idx, new)
        self._last_clicked = idx
        self._update_count()
        return "break"

    def _all(self) -> None:
        for e in self._visible():
            self._set(e.index, True)
        self._update_count()

    def _none(self) -> None:
        for e in self._visible():
            self._set(e.index, False)
        self._update_count()

    def _invert(self) -> None:
        for e in self._visible():
            self._set(e.index, e.index not in self.checked)
        self._update_count()

    def _update_count(self) -> None:
        n = len(self.checked)
        self.count_lbl.configure(text=f"Zaznaczono {n} z {len(self.result.entries)}")
        self.ok_btn.configure(state="normal" if n else "disabled", text=f"Dodaj zaznaczone ({n})")

    def _ok(self) -> None:
        chosen = [e for e in self.result.entries if e.index in self.checked]
        self.close()
        self.on_ok(chosen)


# =============================================================================
# Formats
# =============================================================================
NONE_IID = "__none__"


def _size(f: FormatInfo) -> str:
    if not f.filesize:
        return ""
    return ("~" if f.approx else "") + human_bytes(f.filesize)


class FormatDialog(Modal):
    """Manual video/audio stream picker (the equivalent of `yt-dlp -F` + `-f ID+ID`)."""

    def __init__(self, master, result: ProbeResult, on_ok: Callable[[str, str], None]):
        super().__init__(master, "Wybór formatu", (940, 680))
        self.result = result
        self.on_ok = on_ok
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=3)
        self.grid_rowconfigure(4, weight=2)

        self.videos = sorted(
            (f for f in result.formats if f.kind in ("video", "av")),
            key=lambda f: (f.height or 0, f.fps or 0, f.tbr or 0),
            reverse=True,
        )
        self.audios = sorted((f for f in result.formats if f.kind == "audio"), key=lambda f: f.abr or 0, reverse=True)
        self.by_id = {f.format_id: f for f in result.formats}

        ctk.CTkLabel(
            self, text=result.title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w", wraplength=880
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))

        ctk.CTkLabel(self, text="Obraz", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=1, column=0, sticky="ew", padx=16
        )
        vcols = [
            Column("id", "ID", 60),
            Column("ext", "Rozsz.", 56),
            Column("res", "Rozdzielczość", 110),
            Column("fps", "FPS", 46, "e"),
            Column("codec", "Kodek", 150),
            Column("tbr", "kb/s", 66, "e"),
            Column("size", "Rozmiar", 84, "e"),
            Column("note", "Uwagi", 240, stretch=True),
        ]
        self.vt = Table(self, vcols, selectmode="browse", height=9)
        self.vt.grid(row=2, column=0, sticky="nsew", padx=14)
        self.vt.tree.insert("", "end", iid=NONE_IID, values=("—", "", "bez obrazu (tylko dźwięk)", "", "", "", "", ""))
        for f in self.videos:
            codec = f.vcodec.split(".")[0] + (f" + {f.acodec.split('.')[0]}" if f.kind == "av" else "")
            note = ", ".join(x for x in (f.note, f.dynamic_range if f.dynamic_range != "SDR" else "", f.protocol) if x)
            self.vt.tree.insert(
                "", "end", iid=f.format_id,
                values=(f.format_id, f.ext, f.resolution, f"{f.fps:g}" if f.fps else "", codec,
                        f"{f.tbr:.0f}" if f.tbr else "", _size(f), note),
            )

        ctk.CTkLabel(self, text="Dźwięk", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=3, column=0, sticky="ew", padx=16, pady=(8, 0)
        )
        acols = [
            Column("id", "ID", 60),
            Column("ext", "Rozsz.", 56),
            Column("codec", "Kodek", 110),
            Column("abr", "kb/s", 66, "e"),
            Column("asr", "Hz", 70, "e"),
            Column("size", "Rozmiar", 84, "e"),
            Column("note", "Uwagi", 300, stretch=True),
        ]
        self.at = Table(self, acols, selectmode="browse", height=6)
        self.at.grid(row=4, column=0, sticky="nsew", padx=14)
        self.at.tree.insert("", "end", iid=NONE_IID, values=("—", "", "bez dźwięku", "", "", "", ""))
        for f in self.audios:
            note = ", ".join(x for x in (f.note, f.protocol) if x)
            self.at.tree.insert(
                "", "end", iid=f.format_id,
                values=(f.format_id, f.ext, f.acodec.split(".")[0], f"{f.abr:.0f}" if f.abr else "",
                        f.asr or "", _size(f), note),
            )

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=14, pady=12)
        bottom.grid_columnconfigure(0, weight=1)
        self.sel_lbl = ctk.CTkLabel(bottom, text="", anchor="w", justify="left")
        self.sel_lbl.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(bottom, text="Anuluj", width=90, command=self.close, **FLAT).grid(row=0, column=1, padx=(6, 0))
        self.ok_btn = ctk.CTkButton(bottom, text="Dodaj do listy", width=150, command=self._ok)
        self.ok_btn.grid(row=0, column=2, padx=(6, 0))

        for t in (self.vt.tree, self.at.tree):
            t.bind("<<TreeviewSelect>>", lambda e: self._update())
        if self.videos:
            self.vt.tree.selection_set(self.videos[0].format_id)
        else:
            self.vt.tree.selection_set(NONE_IID)
        if self.audios:
            self.at.tree.selection_set(self.audios[0].format_id)
        else:
            self.at.tree.selection_set(NONE_IID)
        self._update()

    def _sel(self, tree) -> FormatInfo | None:
        s = tree.selection()
        return self.by_id.get(s[0]) if s and s[0] != NONE_IID else None

    def _spec(self) -> tuple[str, str, str]:
        """(format, mode, description) or ('', '', reason)."""
        v, a = self._sel(self.vt.tree), self._sel(self.at.tree)
        if v is None and a is None:
            return "", "", "Wybierz co najmniej obraz albo dźwięk."
        if v is None:
            return a.format_id, MODE_AUDIO, f"Tylko dźwięk: {a.format_id} — zapis wg formatu audio z panelu opcji."
        if a is None:
            extra = "" if v.kind == "av" else "  ⚠ bez dźwięku"
            return v.format_id, MODE_VIDEO, f"Format: {v.format_id}{extra}"
        total = (v.filesize or 0) + (a.filesize or 0)
        size = f" · razem ~{human_bytes(total)}" if total else ""
        return f"{v.format_id}+{a.format_id}", MODE_VIDEO, f"Format: {v.format_id}+{a.format_id}{size}"

    def _update(self) -> None:
        spec, mode, desc = self._spec()
        self.sel_lbl.configure(text=desc, text_color=("gray10", "gray90") if spec else RED)
        self.ok_btn.configure(state="normal" if spec else "disabled")

    def _ok(self) -> None:
        spec, mode, _ = self._spec()
        if not spec:
            return
        self.close()
        self.on_ok(spec, mode)


# =============================================================================
# Settings
# =============================================================================
class SettingsDialog(Modal):
    def __init__(self, master, settings: Settings, on_save: Callable[[], None]):
        super().__init__(master, "Ustawienia", (700, 720))
        self.s = settings
        self.on_save = on_save
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew", padx=6, pady=(6, 0))
        body.grid_columnconfigure(1, weight=1)
        r = 0

        def section(text: str) -> None:
            nonlocal r
            ctk.CTkLabel(body, text=text, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(
                row=r, column=0, columnspan=3, sticky="ew", padx=8, pady=(12 if r else 4, 4)
            )
            r += 1

        def hint(text: str) -> None:
            nonlocal r
            ctk.CTkLabel(body, text=text, text_color=GRAY, anchor="w", justify="left", wraplength=600).grid(
                row=r, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 4)
            )
            r += 1

        def check(text: str, value: bool) -> ctk.BooleanVar:
            nonlocal r
            var = ctk.BooleanVar(value=value)
            ctk.CTkCheckBox(body, text=text, variable=var).grid(
                row=r, column=0, columnspan=3, sticky="w", padx=12, pady=3
            )
            r += 1
            return var

        # --- Downloading -------------------------------------------------------
        section("Pobieranie")
        ctk.CTkLabel(body, text="Nazwa pliku:").grid(row=r, column=0, sticky="w", padx=12)
        self.tpl_var = ctk.StringVar(value=settings.template)
        ctk.CTkEntry(body, textvariable=self.tpl_var).grid(row=r, column=1, sticky="ew", padx=(6, 6))
        ctk.CTkButton(body, text="Domyślna", width=80, command=lambda: self.tpl_var.set(DEFAULT_TEMPLATE), **FLAT).grid(
            row=r, column=2, padx=(0, 8)
        )
        r += 1
        hint("Szablon yt-dlp, np. %(uploader)s/%(title)s [%(id)s].%(ext)s — ukośnik tworzy podfolder.")
        ctk.CTkLabel(body, text="Limit prędkości:").grid(row=r, column=0, sticky="w", padx=12)
        self.rate_var = ctk.StringVar(value=settings.rate_limit)
        ctk.CTkEntry(body, textvariable=self.rate_var, width=120, placeholder_text="bez limitu").grid(
            row=r, column=1, sticky="w", padx=(6, 6)
        )
        r += 1
        hint("Na każde pobieranie, np. 5M (5 MB/s) albo 800K. Puste = bez limitu.")

        # --- Queue -------------------------------------------------------------
        section("Kolejka")
        self.autostart_var = check("Uruchamiaj zadanie od razu po dodaniu do listy", settings.autostart)
        self.restore_var = check("Przywracaj niezakończone zadania po ponownym uruchomieniu", settings.restore_queue)

        # --- Subtitles ---------------------------------------------------------
        section("Napisy (tryb wideo)")
        self.sub_auto_var = check("Także napisy generowane automatycznie / tłumaczone", settings.sub_auto)
        self.sub_embed_var = check("Osadzaj napisy w pliku wideo (inaczej osobne pliki .srt)", settings.sub_embed)
        hint("Włączanie napisów i języki (np. pl,en) — w panelu opcji okna głównego.")

        # --- SponsorBlock --------------------------------------------------------
        section("SponsorBlock — kategorie")
        cats = set(settings.sb_categories.split(","))
        self.sb_vars: dict[str, ctk.BooleanVar] = {}
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.grid(row=r, column=0, columnspan=3, sticky="ew", padx=8)
        r += 1
        for i, cat in enumerate(SB_ALL_CATEGORIES):
            var = ctk.BooleanVar(value=cat in cats)
            ctk.CTkCheckBox(grid, text=SB_LABELS.get(cat, cat), variable=var).grid(
                row=i // 2, column=i % 2, sticky="w", padx=4, pady=3
            )
            self.sb_vars[cat] = var
        hint("Tryb (oznacz rozdziały / wytnij) wybierasz w panelu opcji. Dane: sponsor.ajay.app.")

        # --- Cookies -------------------------------------------------------------
        section("Cookies (filmy z ograniczeniem wieku, prywatne, członkowskie)")
        ctk.CTkLabel(body, text="Z przeglądarki:").grid(row=r, column=0, sticky="w", padx=12)
        self.browser_var = ctk.StringVar(value=settings.cookies_browser or "brak")
        ctk.CTkOptionMenu(
            body, values=["brak"] + [b for b in COOKIE_BROWSERS if b], variable=self.browser_var, width=140
        ).grid(row=r, column=1, sticky="w", padx=(6, 6))
        r += 1
        ctk.CTkLabel(body, text="Plik cookies.txt:").grid(row=r, column=0, sticky="w", padx=12, pady=(4, 0))
        self.cfile_var = ctk.StringVar(value=settings.cookies_file)
        ctk.CTkEntry(body, textvariable=self.cfile_var).grid(row=r, column=1, sticky="ew", padx=(6, 6), pady=(4, 0))
        ctk.CTkButton(body, text="Wybierz…", width=80, command=self._pick_cookies, **FLAT).grid(
            row=r, column=2, padx=(0, 8), pady=(4, 0)
        )
        r += 1
        hint(
            "Plik ma pierwszeństwo przed przeglądarką. Chrome/Edge na Windows szyfrują cookies w sposób, "
            "którego yt-dlp zwykle nie odczyta — najpewniej działa Firefox albo wyeksportowany cookies.txt. "
            "Przeglądarka powinna być zamknięta podczas odczytu."
        )

        # --- Other ---------------------------------------------------------------
        section("Inne")
        self.paste_var = check("Wklejaj link ze schowka po przełączeniu na okno (gdy pole jest puste)", settings.auto_paste)
        self.watch_var = check(
            "Obserwuj schowek — skopiowany link YouTube od razu trafia na listę", settings.watch_clipboard
        )
        self.notify_var = check("Dźwięk i mignięcie paska zadań po zakończeniu listy", settings.notify_done)
        self.verbose_var = check("Szczegółowy log (komunikaty [debug] yt-dlp)", settings.verbose_log)

        # --- buttons ------------------------------------------------------------
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="ew", padx=14, pady=12)
        bottom.grid_columnconfigure(0, weight=1)
        self.err_lbl = ctk.CTkLabel(bottom, text="", text_color=RED, anchor="w")
        self.err_lbl.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(bottom, text="Anuluj", width=90, command=self.close, **FLAT).grid(row=0, column=1, padx=(6, 0))
        ctk.CTkButton(bottom, text="Zapisz", width=110, command=self._save).grid(row=0, column=2, padx=(6, 0))

    def _pick_cookies(self) -> None:
        p = filedialog.askopenfilename(
            parent=self, title="Plik cookies.txt", filetypes=[("Cookies", "*.txt"), ("Wszystkie", "*.*")]
        )
        if p:
            self.cfile_var.set(p)

    def _save(self) -> None:
        tpl = self.tpl_var.get().strip() or DEFAULT_TEMPLATE
        if "%(ext)s" not in tpl:
            self.err_lbl.configure(text="Szablon nazwy musi zawierać %(ext)s.")
            return
        rate = self.rate_var.get().strip().upper()
        if rate and not RATE_RE.match(rate):
            self.err_lbl.configure(text="Limit prędkości: liczba z jednostką K/M/G, np. 5M.")
            return
        cats = [c for c, v in self.sb_vars.items() if v.get()]
        s = self.s
        s.template = tpl
        s.rate_limit = rate
        s.autostart = bool(self.autostart_var.get())
        s.restore_queue = bool(self.restore_var.get())
        s.sub_auto = bool(self.sub_auto_var.get())
        s.sub_embed = bool(self.sub_embed_var.get())
        s.sb_categories = ",".join(cats) or SB_DEFAULT_CATEGORIES
        b = self.browser_var.get()
        s.cookies_browser = "" if b == "brak" else b
        s.cookies_file = self.cfile_var.get().strip()
        s.auto_paste = bool(self.paste_var.get())
        s.verbose_log = bool(self.verbose_var.get())
        s.watch_clipboard = bool(self.watch_var.get())
        s.notify_done = bool(self.notify_var.get())
        s.save()
        self.close()
        self.on_save()
