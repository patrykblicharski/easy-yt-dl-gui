from pathlib import Path

from ytddlg.core.files import related_files
from ytddlg.core.options import MODE_AUDIO, DownloadRequest
from ytddlg.gui.app import dup_key
from ytddlg.gui.queue_view import ACTION_SEP, ACTIONS, progress_bar


def test_dup_key_same_file_only():
    a = DownloadRequest("https://y/1", Path("."))
    assert dup_key(a) == dup_key(DownloadRequest("https://y/1 ", Path("."), video_quality="720p"))
    assert dup_key(a) != dup_key(DownloadRequest("https://y/1", Path("."), container="MP4"))
    assert dup_key(a) != dup_key(DownloadRequest("https://y/1", Path("."), mode=MODE_AUDIO))
    assert dup_key(a) != dup_key(DownloadRequest("https://y/1", Path("."), format_override="18"))


def test_progress_bar():
    assert progress_bar(0.0) == "░" * 10 + "   0%"
    assert progress_bar(0.5).startswith("█" * 5 + "░" * 5)
    assert progress_bar(1.0).endswith("100%")


def test_actions_defined_for_every_state():
    from ytddlg.core.queue import State

    assert set(ACTIONS) == set(State)
    assert [k for _, k in ACTIONS[State.DONE]] == ["play", "folder", "delete"]
    assert ACTION_SEP.strip() == ""


def test_related_files(tmp_path):
    v = tmp_path / "Film [id].mkv"
    v.write_bytes(b"x")
    (tmp_path / "Film [id].pl.srt").write_text("1")
    (tmp_path / "Film [id] 2.mkv").write_bytes(b"x")  # different file — must not be touched
    names = sorted(p.name for p in related_files(v))
    assert names == ["Film [id].mkv", "Film [id].pl.srt"]
