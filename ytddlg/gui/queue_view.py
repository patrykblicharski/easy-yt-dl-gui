"""Compact queue table: action bar, clickable per-row actions column,
context menu and a details line."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from .. import APP_TITLE
from ..core.files import move_to_trash, related_files
from ..core.options import command_line
from ..core.queue import DownloadQueue, State, Task
from . import theme
from .fmt import human_bytes, human_eta, human_speed
from .tree import Column, Table, tree_font

STATE_TAG = {
    State.IDLE: (),
    State.PENDING: ("pending",),
    State.RUNNING: ("running",),
    State.DONE: ("done",),
    State.ERROR: ("error",),
    State.CANCELLED: ("cancelled",),
}

STATE_ICON = {
    State.IDLE: "○",
    State.PENDING: "◔",
    State.RUNNING: "◉",
    State.DONE: "✔",
    State.ERROR: "✖",
    State.CANCELLED: "⊘",
}

# Clickable actions in the Actions column — (label, key)
ACTIONS = {
    State.IDLE: [("▶ Start", "start"), ("✕ Usuń", "remove")],
    State.PENDING: [("■ Anuluj", "cancel")],
    State.RUNNING: [("■ Anuluj", "cancel")],
    State.DONE: [("▶ Odtwórz", "play"), ("▤ Folder", "folder"), ("✕ Usuń", "delete")],
    State.ERROR: [("↻ Ponów", "start"), ("✕ Usuń", "remove")],
    State.CANCELLED: [("↻ Ponów", "start"), ("✕ Usuń", "remove")],
}
ACTION_SEP = "   "
CELL_PAD = 6  # approximate inner padding of a Treeview cell

COLUMNS = [
    Column("nr", "#", 44, "w"),
    Column("title", "Tytuł", 240, "w"),  # width adjusted in _fit_title
    Column("mode", "Tryb", 150),
    Column("progress", "Postęp", 124),
    Column("speed", "Prędkość", 74, "e"),
    Column("eta", "Zostało", 58, "e"),
    Column("status", "Status", 136),
    Column("actions", "Akcje", 214),  # width adjusted in _fit_actions_column
]


def open_path(path) -> None:
    """Opens a file/folder with the system default program (Windows, Linux, macOS)."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, AttributeError):
        pass


def show_in_folder(path) -> None:
    """Shows the file in the file manager (selected, on Windows)."""
    if not path:
        return
    if sys.platform == "win32" and os.path.exists(path):
        subprocess.Popen(f'explorer /select,"{path}"')
    elif sys.platform == "darwin" and os.path.exists(path):
        subprocess.Popen(["open", "-R", str(path)])
    else:
        open_path(os.path.dirname(str(path)))


def progress_bar(fraction: float, width: int = 10) -> str:
    filled = int(round(fraction * width))
    return "█" * filled + "░" * (width - filled) + f" {fraction * 100:3.0f}%"


class QueueView(ctk.CTkFrame):
    def __init__(self, master, dq: DownloadQueue, on_parallel: Callable[[str], None], parallel: int, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(master, **kw)
        self.dq = dq
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- action bar ------------------------------------------------------
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        bar.grid_columnconfigure(6, weight=1)
        ctk.CTkLabel(bar, text="Lista pobierania", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=(2, 12)
        )
        small = {"height": 28}
        self.start_all_btn = ctk.CTkButton(
            bar, text="▶  Pobierz wszystkie", width=170, font=ctk.CTkFont(weight="bold"), command=self.start_all,
            fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER, **small,
        )
        self.start_all_btn.grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(
            bar, text="▶ Zaznaczone", width=104, command=self.start_selected,
            fg_color=theme.INFO, hover_color=theme.INFO_HOVER, **small,
        ).grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(
            bar, text="■ Anuluj", width=86, command=self.cancel_selected,
            fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER, **small,
        ).grid(row=0, column=3, padx=(0, 6))
        ctk.CTkButton(bar, text="✕ Usuń z listy", width=106, command=self.remove_selected, **theme.FLAT, **small).grid(
            row=0, column=4, padx=(0, 6)
        )
        retry = ctk.CTkFrame(bar, fg_color="transparent")
        retry.grid(row=0, column=5, padx=(0, 6), sticky="w")
        ctk.CTkButton(retry, text="↻ Ponów błędy", width=104, command=self.dq.retry_failed, **theme.FLAT, **small).pack(
            side="left", padx=(0, 6)
        )
        ctk.CTkButton(retry, text="Wyczyść gotowe", width=112, command=self.dq.clear_finished, **theme.FLAT, **small).pack(
            side="left"
        )
        self.counts_frame = ctk.CTkFrame(bar, fg_color="transparent")
        self.counts_frame.grid(row=0, column=6, sticky="e", padx=(6, 10))
        ctk.CTkLabel(bar, text="Równolegle:", text_color=theme.MUTED).grid(row=0, column=7, padx=(0, 4))
        self.par_var = ctk.StringVar(value=str(parallel))
        ctk.CTkOptionMenu(
            bar, values=["1", "2", "3", "4", "6"], variable=self.par_var, width=58, command=on_parallel,
            fg_color=theme.FLAT_BTN, button_color=theme.FLAT_HOVER, button_hover_color=theme.FLAT_HOVER,
            text_color=theme.TEXT, **small,
        ).grid(row=0, column=8)

        # --- table -------------------------------------------------------------
        self.table = Table(self, COLUMNS, selectmode="extended", height=8)
        self.table.grid(row=1, column=0, sticky="nsew")
        self.tree = self.table.tree
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_detail(), add="+")
        self.tree.bind("<Button-1>", self._on_click, add="+")
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Motion>", self._on_motion)
        self.tree.bind("<Leave>", lambda e: self.tree.configure(cursor=""))
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<Return>", lambda e: self.start_selected())
        self.tree.bind("<Control-a>", lambda e: (self.tree.selection_set(self.tree.get_children()), "break")[1])
        self._font = tree_font(self.tree)
        self._fit_actions_column()
        self.tree.bind("<Configure>", lambda e: self._fit_title(e.width), add="+")

        # --- selection details -------------------------------------------------
        self.detail = ctk.CTkLabel(self, text="", anchor="w", justify="left", text_color=theme.MUTED, height=20)
        self.detail.grid(row=2, column=0, sticky="ew", padx=6, pady=(4, 0))
        self.bind("<Configure>", lambda e: self.detail.configure(wraplength=max(200, e.width - 30)))

        self.empty_hint = ctk.CTkLabel(
            self.table, text="Lista jest pusta — wklej link, wybierz tryb i kliknij „Dodaj do listy”.",
            text_color=theme.MUTED, fg_color=theme.CARD,
        )
        self.menu = tk.Menu(self, tearoff=0)
        self._refresh_counts()

    # --- selection ---------------------------------------------------------
    def selected_ids(self) -> list[int]:
        return [int(i) for i in self.tree.selection()]

    def _selected_tasks(self) -> list[Task]:
        return [t for t in (self.dq.get(i) for i in self.selected_ids()) if t is not None]

    # --- bulk actions ------------------------------------------------------------
    def start_all(self) -> None:
        self.dq.start_all()

    def start_selected(self) -> None:
        self.dq.start(self.selected_ids())

    def cancel_selected(self) -> None:
        for tid in self.selected_ids():
            self.dq.cancel(tid)

    def remove_selected(self) -> None:
        for tid in self.selected_ids():
            self.dq.remove(tid)

    # --- per-row actions -----------------------------------------------------------
    def _fit_actions_column(self) -> None:
        """The actions column must fit the longest label set — otherwise the last one gets clipped."""
        need = max(self._font.measure(ACTION_SEP.join(lbl for lbl, _ in acts)) for acts in ACTIONS.values())
        need += 2 * CELL_PAD + 12
        self.tree.column("actions", width=need, minwidth=need, stretch=False)
        self._fit_title(self.tree.winfo_width())

    def _fit_title(self, tree_width: int) -> None:
        """The title takes the remaining space so the actions column is always visible."""
        if tree_width <= 1:
            return
        fixed = sum(int(self.tree.column(c.id, "width")) for c in COLUMNS if c.id != "title")
        self.tree.column("title", width=max(120, tree_width - fixed - 2))

    def _action_at(self, event) -> tuple[Task, str] | None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return None
        col = self.tree.identify_column(event.x)
        if col != f"#{len(COLUMNS)}":
            return None
        iid = self.tree.identify_row(event.y)
        task = self.dq.get(int(iid)) if iid else None
        if task is None:
            return None
        bbox = self.tree.bbox(iid, "actions")
        if not bbox:
            return None
        x = event.x - bbox[0] - CELL_PAD
        acts = ACTIONS[task.state]
        sep_w = self._font.measure(ACTION_SEP)
        pos = 0
        for i, (label, key) in enumerate(acts):
            w = self._font.measure(label)
            # boundary = half of the gap after the label
            right = pos + w + (sep_w / 2 if i < len(acts) - 1 else sep_w)
            if -CELL_PAD <= x <= right:
                return task, key
            pos += w + sep_w
        return None

    def _on_motion(self, event) -> None:
        self.tree.configure(cursor="hand2" if self._action_at(event) else "")

    def _on_click(self, event):
        hit = self._action_at(event)
        if hit is None:
            return None
        task, key = hit
        self.run_action(task, key)
        return "break"

    def run_action(self, task: Task, key: str) -> None:
        if key == "start":
            self.dq.start([task.id])
        elif key == "cancel":
            self.dq.cancel(task.id)
        elif key == "remove":
            self.dq.remove(task.id)
        elif key == "play" and task.result_path:
            if task.result_path.exists():
                open_path(task.result_path)
            else:
                messagebox.showwarning(APP_TITLE, f"Plik już nie istnieje:\n{task.result_path}", parent=self)
        elif key == "folder":
            if task.result_path and task.result_path.exists():
                show_in_folder(task.result_path)
            else:
                open_path(task.request.out_dir)
        elif key == "delete":
            self.delete_files([task])

    def delete_files(self, tasks: list[Task]) -> None:
        tasks = [t for t in tasks if t.state == State.DONE]
        if not tasks:
            return
        files = [f for t in tasks if t.result_path for f in related_files(t.result_path)]
        if not files:
            for t in tasks:
                self.dq.remove(t.id)
            return
        names = "\n".join(f"• {f.name}" for f in files[:8]) + ("\n…" if len(files) > 8 else "")
        ans = messagebox.askyesnocancel(
            APP_TITLE,
            f"Przenieść do Kosza {len(files)} plik(ów) i usunąć z listy?\n\n{names}\n\n"
            "Tak — do Kosza i z listy\nNie — tylko z listy (plik zostaje)",
            parent=self,
        )
        if ans is None:
            return
        failed = []
        if ans:
            for f in files:
                try:
                    move_to_trash(f)
                except OSError as e:
                    failed.append(str(e))
        for t in tasks:
            self.dq.remove(t.id)
        if failed:
            messagebox.showerror(APP_TITLE, "Nie wszystkie pliki udało się usunąć:\n\n" + "\n".join(failed), parent=self)

    def _on_double(self, event) -> None:
        if self._action_at(event):
            return
        iid = self.tree.identify_row(event.y)
        task = self.dq.get(int(iid)) if iid else None
        if task is None:
            return
        if task.state == State.DONE:
            self.run_action(task, "play")
        elif task.state.startable:
            self.dq.start([task.id])

    def _on_right_click(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid and iid not in self.tree.selection():
            self.tree.selection_set(iid)
        tasks = self._selected_tasks()
        m = self.menu
        m.delete(0, "end")
        if not tasks:
            m.add_command(label="Pobierz wszystkie dodane", command=self.start_all)
        else:
            one = tasks[0] if len(tasks) == 1 else None
            any_startable = any(t.state.startable for t in tasks)
            any_active = any(t.state.active for t in tasks)
            any_done = any(t.state == State.DONE for t in tasks)
            m.add_command(label="▶  Start", command=self.start_selected, state="normal" if any_startable else "disabled")
            m.add_command(label="■  Anuluj", command=self.cancel_selected, state="normal" if any_active else "disabled")
            m.add_separator()
            done_one = one is not None and one.state == State.DONE and one.result_path is not None
            m.add_command(
                label="▶  Odtwórz", command=lambda: self.run_action(one, "play"),
                state="normal" if done_one else "disabled",
            )
            m.add_command(
                label="▤  Pokaż w folderze", command=lambda: self.run_action(one, "folder"),
                state="normal" if one else "disabled",
            )
            m.add_separator()
            m.add_command(label="Kopiuj link", command=lambda: self._copy("\n".join(t.request.url for t in tasks)))
            m.add_command(
                label="Kopiuj komendę yt-dlp",
                command=lambda: self._copy("\n".join(command_line(t.request, self.dq.tools) for t in tasks)),
            )
            m.add_separator()
            m.add_command(
                label="✕  Usuń plik (do Kosza)…", command=lambda: self.delete_files(tasks),
                state="normal" if any_done else "disabled",
            )
            m.add_command(label="Usuń z listy", command=self.remove_selected)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    # --- rows -------------------------------------------------------------------
    def add_task(self, task: Task) -> None:
        iid = str(task.id)
        if not self.tree.exists(iid):
            self.tree.insert("", "end", iid=iid, values=self._values(task), tags=self._tags(task))
        self._refresh_counts()

    def remove_task(self, task_id: int) -> None:
        iid = str(task_id)
        if self.tree.exists(iid):
            self.tree.delete(iid)
        self._refresh_counts()
        self._update_detail()

    def refresh_task(self, task_id: int) -> None:
        task = self.dq.get(task_id)
        iid = str(task_id)
        if task is None or not self.tree.exists(iid):
            return
        self.tree.item(iid, values=self._values(task))
        self.table.set_tags(iid, self._tags(task))
        if iid in self.tree.selection():
            self._update_detail()

    def _tags(self, t: Task) -> tuple:
        return STATE_TAG[t.state]

    def _values(self, t: Task) -> tuple:
        title = t.request.title or t.request.url
        progress = speed = eta = ""
        p = t.progress
        if t.state == State.RUNNING:
            progress = progress_bar(p.fraction) if p is not None and p.fraction is not None else "…"
            if p is not None and t.stage == p.stage:
                speed = human_speed(p.speed)
                eta = human_eta(p.eta)
            status = t.stage or "Start…"
        elif t.state == State.DONE:
            progress = progress_bar(1.0)
            size = ""
            try:
                if t.result_path and t.result_path.exists():
                    size = human_bytes(t.result_path.stat().st_size)
                elif t.result_path:
                    size = "plik usunięty"
            except OSError:
                pass
            status = f"Gotowe · {size}" if size else "Gotowe"
        elif t.state == State.ERROR:
            status = f"Błąd: {t.error}"
        elif t.state == State.IDLE and t.error:
            status = "Dodane (wcześniej błąd)"
        else:
            status = t.state.value
        actions = ACTION_SEP.join(label for label, _ in ACTIONS[t.state])
        nr = f"{STATE_ICON[t.state]} {t.id}"
        return (nr, title, t.request.label(), progress, speed, eta, status, actions)

    # --- counters ("pills") -------------------------------------------------------
    def _refresh_counts(self) -> None:
        c = self.dq.counts()
        for w in self.counts_frame.winfo_children():
            w.destroy()
        pills = [
            (c[State.IDLE], "dodane", theme.FLAT_BTN, theme.TEXT),
            (c[State.RUNNING] + c[State.PENDING], "w toku", theme.INFO, "white"),
            (c[State.DONE], "gotowe", theme.SUCCESS, "white"),
            (c[State.ERROR], "błędy", theme.DANGER, "white"),
        ]
        for n, label, bg, fg in pills:
            if n:
                ctk.CTkLabel(
                    self.counts_frame, text=f" {n} {label} ", fg_color=bg, text_color=fg, corner_radius=10, height=22,
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).pack(side="left", padx=2)
        idle = c[State.IDLE]
        self.start_all_btn.configure(
            state="normal" if idle else "disabled",
            text=f"▶  Pobierz wszystkie ({idle})" if idle else "▶  Pobierz wszystkie",
        )
        if self.tree.get_children():
            self.empty_hint.place_forget()
        else:
            self.empty_hint.place(relx=0.5, rely=0.55, anchor="center")

    def _update_detail(self) -> None:
        tasks = self._selected_tasks()
        if not tasks:
            self.detail.configure(text="", text_color=theme.MUTED)
            return
        if len(tasks) > 1:
            self.detail.configure(text=f"Zaznaczono {len(tasks)} pozycji", text_color=theme.MUTED)
            return
        t = tasks[0]
        if t.state == State.ERROR or (t.state == State.IDLE and t.error):
            self.detail.configure(text=f"{t.request.title} — {t.error}", text_color=theme.RED_TEXT)
        elif t.state == State.DONE and t.result_path:
            self.detail.configure(text=f"✔ {t.result_path}", text_color=theme.GREEN_TEXT)
        else:
            self.detail.configure(text=f"{t.request.title} — {t.request.url}", text_color=theme.MUTED)

    def on_state_change(self) -> None:
        self._refresh_counts()

    def restyle(self) -> None:
        self.table.restyle()
        self._font = tree_font(self.tree)
        self._fit_actions_column()
