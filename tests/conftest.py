"""Tests never touch the user's real settings (%APPDATA%\\ytddlg)."""

import pytest


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("YTDDLG_CONFIG_DIR", str(tmp_path / "config"))
