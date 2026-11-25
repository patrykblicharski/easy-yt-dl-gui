"""Queue tests without network: run_download is replaced with a fake."""

import threading
import time
from pathlib import Path

import pytest

import ytddlg.core.queue as qmod
from ytddlg.core.downloader import CancelledByUser, Progress
from ytddlg.core.options import DownloadRequest
from ytddlg.core.queue import DownloadQueue, State


@pytest.fixture
def fake_download(monkeypatch):
    calls = []

    def fake(req, tools, on_progress, on_stage, on_log, cancel_event, verbose=False):
        calls.append(req.url)
        for i in range(1, 21):
            if cancel_event.is_set():
                raise CancelledByUser("x")
            on_progress(Progress(i / 20, i, 20, 1000.0, 1, "Pobieranie"))
            time.sleep(0.01)
        if req.url == "bad":
            raise RuntimeError("ERROR: Video unavailable")
        return Path(req.out_dir) / f"{req.url}.mkv"

    monkeypatch.setattr(qmod, "run_download", fake)
    return calls


def wait(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_add_does_not_start(fake_download):
    q = DownloadQueue(None)
    t = q.add(DownloadRequest("a", Path(".")))
    time.sleep(0.2)
    assert t.state == State.IDLE
    assert fake_download == []


def test_start_all_respects_parallel(fake_download):
    q = DownloadQueue(None, max_parallel=2)
    tasks = [q.add(DownloadRequest(u, Path("."))) for u in ("a", "b", "c", "bad")]
    assert q.start_all() == 4
    running = sum(1 for t in tasks if t.state == State.RUNNING)
    assert running == 2
    assert wait(lambda: all(t.state.finished for t in tasks))
    assert [t.state for t in tasks] == [State.DONE, State.DONE, State.DONE, State.ERROR]
    assert tasks[3].error == "Video unavailable"
    # retry the failed one
    q.retry(tasks[3].id)
    assert wait(lambda: tasks[3].state.finished)


def test_add_with_start(fake_download):
    q = DownloadQueue(None)
    t = q.add(DownloadRequest("a", Path(".")), start=True)
    assert wait(lambda: t.state == State.DONE)


def test_start_selected_only(fake_download):
    q = DownloadQueue(None)
    a = q.add(DownloadRequest("a", Path(".")))
    b = q.add(DownloadRequest("b", Path(".")))
    q.start([b.id])
    assert wait(lambda: b.state == State.DONE)
    assert a.state == State.IDLE


def test_cancel_running(fake_download):
    q = DownloadQueue(None)
    t = q.add(DownloadRequest("a", Path(".")), start=True)
    q.cancel(t.id)
    assert wait(lambda: t.state == State.CANCELLED)


def test_save_and_load(tmp_path, fake_download):
    q = DownloadQueue(None)
    a = q.add(DownloadRequest("a", tmp_path, title="A"))
    q.add(DownloadRequest("b", tmp_path, title="B", subs=True))
    q.start([a.id])
    assert wait(lambda: a.state == State.DONE)
    f = tmp_path / "queue.json"
    q.save(f)
    q2 = DownloadQueue(None)
    assert q2.load(f) == 1  # DONE tasks are not saved
    (t,) = q2.tasks()
    assert t.state == State.IDLE and t.request.title == "B" and t.request.subs is True


def test_remove_running_removes_after_stop(fake_download):
    q = DownloadQueue(None)
    t = q.add(DownloadRequest("a", Path(".")), start=True)
    q.remove(t.id)
    assert wait(lambda: q.get(t.id) is None)
