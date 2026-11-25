"""ttk.Treeview styled to match CustomTkinter (light/dark theme, DPI scaling).

A Treeview instead of rows of CTk widgets: compact, fast with hundreds of entries,
with multi-row selection.

Note: in Tk 8.6.10+ a tag background wins over the style's selection colour, so the
selection is an extra "sel" tag configured last (highest priority).
"""

from __future__ import annotations

from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk

import customtkinter as ctk

from . import theme

STYLE = "Ctk.Treeview"


@dataclass
class Column:
    id: str
    heading: str
    width: int
    anchor: str = "w"
    stretch: bool = False


def pick(pair):
    if isinstance(pair, (list, tuple)):
        return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]
    return pair


def apply_style(widget) -> None:
    """(Re)configures the style — call after a theme change."""
    style = ttk.Style(widget)
    if style.theme_use() != "clam":
        style.theme_use("clam")
    bg = pick(theme.TREE_BG)
    fg = pick(theme.TEXT)
    scaling = ctk.ScalingTracker.get_widget_scaling(widget)
    row_h = int(24 * scaling)
    base = tkfont.nametofont("TkDefaultFont").actual()
    style.configure(
        STYLE,
        background=bg,
        fieldbackground=bg,
        foreground=fg,
        rowheight=row_h,
        borderwidth=0,
        relief="flat",
        font=(base["family"], 10),
    )
    style.map(
        STYLE,
        background=[("selected", pick(theme.SELECTED))],
        foreground=[("selected", pick(theme.SELECTED_TEXT))],
    )
    style.configure(
        f"{STYLE}.Heading",
        background=pick(theme.HEADING),
        foreground=pick(theme.MUTED),
        relief="flat",
        borderwidth=0,
        padding=(6, 4),
        font=(base["family"], 9, "bold"),
    )
    style.map(f"{STYLE}.Heading", background=[("active", pick(theme.FLAT_HOVER))])
    style.layout(STYLE, [("Treeview.treearea", {"sticky": "nswe"})])


def apply_tags(tree: ttk.Treeview) -> None:
    dark = ctk.get_appearance_mode() == "Dark"
    tree.tag_configure("odd", background=pick(("#f8f9fc", "#232838")))
    for tag, (bl, bd, fl, fd) in theme.ROW_COLORS.items():
        bg = bd if dark else bl
        kw = {"foreground": fd if dark else fl}
        if bg:
            kw["background"] = bg
        tree.tag_configure(tag, **kw)
    # configured last => highest priority
    tree.tag_configure("sel", background=pick(theme.SELECTED), foreground=pick(theme.SELECTED_TEXT))


def tree_font(tree: ttk.Treeview) -> tkfont.Font:
    spec = ttk.Style(tree).lookup(STYLE, "font") or "TkDefaultFont"
    return tkfont.Font(font=spec)


class Table(ctk.CTkFrame):
    """Treeview + scrollbar inside a CTk frame."""

    def __init__(self, master, columns: list[Column], selectmode: str = "extended", height: int = 10, **kw):
        kw.setdefault("fg_color", theme.CARD)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", theme.CARD_BORDER)
        kw.setdefault("corner_radius", 8)
        super().__init__(master, **kw)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        apply_style(self)
        self.tree = ttk.Treeview(
            self,
            columns=[c.id for c in columns],
            show="headings",
            selectmode=selectmode,
            style=STYLE,
            height=height,
        )
        scaling = ctk.ScalingTracker.get_widget_scaling(self)
        for c in columns:
            self.tree.heading(c.id, text=c.heading, anchor=c.anchor)
            self.tree.column(
                c.id, width=int(c.width * scaling), minwidth=int(30 * scaling), anchor=c.anchor, stretch=c.stretch
            )
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        self.vsb = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.vsb.grid(row=0, column=1, sticky="ns", padx=(0, 2), pady=4)
        self.tree.configure(yscrollcommand=self.vsb.set)
        apply_tags(self.tree)
        self.tree.bind("<<TreeviewSelect>>", self._sync_sel_tags, add="+")

    def _sync_sel_tags(self, _event=None) -> None:
        sel = set(self.tree.selection())
        for iid in self.tree.get_children():
            tags = [t for t in self.tree.item(iid, "tags") if t != "sel"]
            if iid in sel:
                tags.append("sel")
            self.tree.item(iid, tags=tags)

    def set_tags(self, iid: str, tags) -> None:
        tags = [t for t in tags if t != "sel"]
        if iid in self.tree.selection():
            tags.append("sel")
        self.tree.item(iid, tags=tags)

    def restyle(self) -> None:
        apply_style(self)
        apply_tags(self.tree)
