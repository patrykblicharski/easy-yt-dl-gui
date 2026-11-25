"""Tests against real YouTube. Run only with YTDDLG_NETWORK=1."""

import os
import threading
import time

import pytest

from ytddlg.core.downloader import CancelledByUser, run_download
from ytddlg.core.options import MODE_AUDIO, DownloadRequest
from ytddlg.core.probe import probe
from ytddlg.core.queue import DownloadQueue, State
from ytddlg.core.tools import detect_tools

pytestmark = pytest.mark.skipif(os.environ.get("YTDDLG_NETWORK") != "1", reason="ustaw YTDDLG_NETWORK=1")

SHORT = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo", 19 s
HD = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"  # Big Buck Bunny 4K60
TOOLS = detect_tools()


def test_probe_video():
    r = probe(HD, TOOLS)
    assert r.kind == "video"
    assert r.max_height >= 2160
    assert r.thumbnail_bytes
    kinds = {f.kind for f in r.formats}
    assert {"video", "audio"} <= kinds
    assert any(f.format_id == "251" for f in r.formats)


def test_probe_playlist():
    # a channel's Videos tab is also a list of entries (more stable than a specific playlist)
    r = probe("https://www.youtube.com/@BlenderStudio/videos", TOOLS, fetch_thumbnail=False)
    assert r.kind == "playlist"
    assert len(r.entries) > 3
    assert r.entries[0].url.startswith("https://") and r.entries[0].index == 1


def test_format_override_and_sponsorblock(tmp_path):
    from ytddlg.core.options import SB_MARK

    req = DownloadRequest(SHORT, tmp_path, format_override="160+139", sponsorblock=SB_MARK)
    path = run_download(req, TOOLS, lambda p: None, lambda s: None, lambda *a: None, threading.Event())
    assert path and path.exists() and path.suffix == ".mkv"


def test_probe_video_in_playlist_link_is_single_video():
    r = probe(SHORT + "&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf", TOOLS, fetch_thumbnail=False)
    assert r.kind == "video"


def test_video_download(tmp_path):
    seen = []
    stages = []
    path = run_download(
        DownloadRequest(SHORT, tmp_path), TOOLS, seen.append, stages.append, lambda *a: None, threading.Event()
    )
    assert path and path.exists() and path.suffix == ".mkv"
    assert seen and seen[-1].fraction == pytest.approx(1.0, abs=0.02)
    assert any("Scalanie" in s for s in stages)


def test_audio_download(tmp_path):
    req = DownloadRequest(SHORT, tmp_path, mode=MODE_AUDIO, audio_format="MP3")
    path = run_download(req, TOOLS, lambda p: None, lambda s: None, lambda *a: None, threading.Event())
    assert path and path.exists() and path.suffix == ".mp3"


def test_cancel(tmp_path):
    ev = threading.Event()

    def on_progress(p):
        ev.set()  # cancel on the first progress report

    with pytest.raises(CancelledByUser):
        run_download(DownloadRequest(HD, tmp_path), TOOLS, on_progress, lambda s: None, lambda *a: None, ev)


def test_queue(tmp_path):
    q = DownloadQueue(TOOLS, max_parallel=2)
    t1 = q.add(DownloadRequest(SHORT, tmp_path / "a"))
    t2 = q.add(DownloadRequest(SHORT, tmp_path / "b", mode=MODE_AUDIO))
    time.sleep(0.3)
    assert t1.state == State.IDLE  # adding does not start the task
    q.start_all()
    deadline = time.time() + 180
    while time.time() < deadline and not (t1.state.finished and t2.state.finished):
        time.sleep(0.5)
    assert t1.state == State.DONE, t1.error
    assert t2.state == State.DONE, t2.error
    assert t2.result_path.suffix == ".opus"
