import time
from pathlib import Path

import ytddlg.core.queue as qmod
from ytddlg.core.downloader import Progress
from ytddlg.core.options import DownloadRequest
from ytddlg.core.queue import DownloadQueue, State
from ytddlg.gui.notify import is_youtube_url


def test_is_youtube_url():
    ok = [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://youtu.be/jNQXAC9IVRw",
        "https://youtube.com/shorts/abc123",
        "https://music.youtube.com/watch?v=x",
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/@BlenderStudio",
    ]
    bad = ["https://example.com/watch?v=x", "youtube.com/watch?v=x", "zwykły tekst", "https://www.youtube.com/"]
    assert all(is_youtube_url(u) for u in ok)
    assert not any(is_youtube_url(u) for u in bad)


def test_retry_failed_and_total_speed(monkeypatch):
    def fake(req, tools, on_progress, on_stage, on_log, cancel_event, verbose=False):
        on_progress(Progress(0.5, 1, 2, 1000.0, 1, "Pobieranie"))
        if req.url == "bad":
            raise RuntimeError("ERROR: x")
        return Path("x.mkv")

    monkeypatch.setattr(qmod, "run_download", fake)
    q = DownloadQueue(None, max_parallel=4)
    good = q.add(DownloadRequest("ok", Path(".")))
    bad = q.add(DownloadRequest("bad", Path(".")))
    q.start_all()
    end = time.time() + 5
    while time.time() < end and not (good.state.finished and bad.state.finished):
        time.sleep(0.02)
    assert bad.state == State.ERROR and good.state == State.DONE
    assert q.total_speed() == 0.0  # nothing is running
    assert q.retry_failed() == 1
    assert bad.state in (State.PENDING, State.RUNNING, State.ERROR)
