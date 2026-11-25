"""Collects every translatable English string used by the app (shared by tests and tooling)."""

from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "ytddlg"
CALL_NAMES = {"t", "tr"}


def literal_keys() -> dict[str, list[str]]:
    """Keys passed as string literals to t()/tr() -> list of 'file:line' locations."""
    found: dict[str, list[str]] = {}
    for path in PKG.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in CALL_NAMES
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.setdefault(node.args[0].value, []).append(f"{path.relative_to(PKG.parent)}:{node.lineno}")
    return found


def dynamic_keys() -> set[str]:
    """Keys that reach t()/tr() through variables (tables of labels)."""
    from ytddlg.core.downloader import STAGE_TEXTS
    from ytddlg.gui.app import APPEARANCE_MODES
    from ytddlg.gui.dialogs import SB_LABELS
    from ytddlg.gui.queue_view import ACTION_KEYS, COLUMN_SPECS

    keys = set(STAGE_TEXTS) | set(APPEARANCE_MODES) | set(SB_LABELS.values())
    keys |= {text for acts in ACTION_KEYS.values() for _, text, _ in acts}
    keys |= {head for _, head, _, _ in COLUMN_SPECS if head != "#"}
    return keys


def all_keys() -> set[str]:
    return set(literal_keys()) | dynamic_keys()


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(PKG.parent))
    for k in sorted(all_keys(), key=str.lower):
        print(repr(k))
