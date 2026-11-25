"""Download queue with a parallelism limit.

Adding a task does NOT start it (IDLE state) — starting is a separate action
(`start`, `start_all`) unless `add(..., start=True)` is used.

Worker threads never touch the GUI: every change is published as an event on a
queue.Queue that the GUI drains on its own thread (Tk is not thread-safe).
"""

from __future__ import annotations

import itertools
import json
import queue
import threading
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from ..i18n import t
from .downloader import CancelledByUser, Progress, run_download
from .options import DownloadRequest
from .tools import Tools


class State(str, Enum):
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        """Translated, human-readable state name."""
        return {
            State.IDLE: t("Added"),
            State.PENDING: t("Waiting"),
            State.RUNNING: t("In progress"),
            State.DONE: t("Done"),
            State.ERROR: t("Error"),
            State.CANCELLED: t("Cancelled"),
        }[self]

    @property
    def finished(self) -> bool:
        return self in (State.DONE, State.ERROR, State.CANCELLED)

    @property
    def active(self) -> bool:
        return self in (State.PENDING, State.RUNNING)

    @property
    def startable(self) -> bool:
        return self in (State.IDLE, State.ERROR, State.CANCELLED)


@dataclass
class Task:
    id: int
    request: DownloadRequest
    state: State = State.IDLE
    stage: str = ""
    progress: Progress | None = None
    result_path: Path | None = None
    error: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event)
    remove_when_done: bool = False


@dataclass
class Event:
    kind: str  # "added" | "state" | "progress" | "stage" | "log" | "removed"
    task_id: int | None
    data: Any = None


def short_error(exc: BaseException) -> str:
    msg = str(exc).strip()
    if msg.startswith("ERROR: "):
        msg = msg[7:]
    # yt-dlp may append long hints — the first line is enough for the table
    return msg.splitlines()[0] if msg else exc.__class__.__name__


class DownloadQueue:
    def __init__(self, tools: Tools | None, max_parallel: int = 2, verbose: bool = False):
        self.tools = tools
        self.max_parallel = max(1, max_parallel)
        self.verbose = verbose
        self.events: "queue.Queue[Event]" = queue.Queue()
        self._tasks: dict[int, Task] = {}
        self._ids = itertools.count(1)
        self._lock = threading.RLock()

    # --- adding / starting -----------------------------------------------------
    def add(self, req: DownloadRequest, start: bool = False) -> Task:
        with self._lock:
            task = Task(id=next(self._ids), request=req, state=State.PENDING if start else State.IDLE)
            self._tasks[task.id] = task
        self._emit("added", task.id, task)
        if start:
            self._pump()
        return task

    def start(self, task_ids: Iterable[int]) -> int:
        """Starts the given tasks (IDLE / ERROR / CANCELLED). Returns how many were started."""
        n = 0
        with self._lock:
            for tid in task_ids:
                task = self._tasks.get(tid)
                if task is None or not task.state.startable:
                    continue
                self._reset(task)
                self._set_state(task, State.PENDING)
                n += 1
        self._pump()
        return n

    def start_all(self) -> int:
        """Starts every task in the IDLE state."""
        return self.start(t.id for t in self.tasks() if t.state == State.IDLE)

    def retry(self, task_id: int) -> None:
        self.start([task_id])

    def retry_failed(self) -> int:
        """Retries every failed or cancelled task."""
        return self.start(t.id for t in self.tasks() if t.state in (State.ERROR, State.CANCELLED))

    def total_speed(self) -> float:
        """Combined download speed (B/s) of running tasks."""
        return sum(
            (t.progress.speed or 0.0)
            for t in self.tasks()
            if t.state == State.RUNNING and t.progress is not None and t.stage == t.progress.stage
        )

    # --- cancelling / removing -------------------------------------------------
    def cancel(self, task_id: int) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or not task.state.active:
                return
            task.cancel_event.set()
            if task.state == State.PENDING:
                self._set_state(task, State.CANCELLED)
        self._pump()

    def cancel_all(self) -> None:
        for t in self.tasks():
            self.cancel(t.id)

    def remove(self, task_id: int) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if task.state == State.RUNNING:
                # The worker removes the task itself once the download stops
                task.remove_when_done = True
                task.cancel_event.set()
                return
            del self._tasks[task_id]
        self._emit("removed", task_id)
        self._pump()

    def clear_finished(self) -> None:
        for t in self.tasks():
            if t.state == State.DONE:
                self.remove(t.id)

    # --- reading -----------------------------------------------------------------
    def get(self, task_id: int) -> Task | None:
        return self._tasks.get(task_id)

    def tasks(self) -> list[Task]:
        with self._lock:
            return list(self._tasks.values())

    def set_max_parallel(self, n: int) -> None:
        self.max_parallel = max(1, n)
        self._pump()

    @property
    def active_count(self) -> int:
        return sum(1 for t in self.tasks() if t.state.active)

    def counts(self) -> dict[State, int]:
        c = {s: 0 for s in State}
        for t in self.tasks():
            c[t.state] += 1
        return c

    # --- saving / loading the queue ---------------------------------------------
    def save(self, path: Path) -> None:
        """Saves unfinished tasks (everything except DONE)."""
        items = [
            {"request": t.request.to_dict(), "error": t.error}
            for t in self.tasks()
            if t.state != State.DONE and not t.remove_when_done
        ]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass

    def load(self, path: Path) -> int:
        """Restores saved tasks as IDLE. Returns their count."""
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        n = 0
        for it in items if isinstance(items, list) else []:
            try:
                req = DownloadRequest.from_dict(it["request"])
            except (KeyError, TypeError, ValueError):
                continue
            task = self.add(req)
            task.error = it.get("error") or ""
            n += 1
        return n

    # --- internals ----------------------------------------------------------
    def _emit(self, kind: str, task_id: int | None, data: Any = None) -> None:
        self.events.put(Event(kind, task_id, data))

    def _set_state(self, task: Task, state: State) -> None:
        task.state = state
        self._emit("state", task.id, state)

    @staticmethod
    def _reset(task: Task) -> None:
        task.cancel_event = threading.Event()
        task.error = ""
        task.progress = None
        task.result_path = None
        task.stage = ""

    def _pump(self) -> None:
        with self._lock:
            running = sum(1 for t in self._tasks.values() if t.state == State.RUNNING)
            for task in self._tasks.values():
                if running >= self.max_parallel:
                    break
                if task.state == State.PENDING:
                    self._set_state(task, State.RUNNING)
                    running += 1
                    threading.Thread(target=self._worker, args=(task,), daemon=True, name=f"dl-{task.id}").start()

    def _worker(self, task: Task) -> None:
        tid = task.id

        def on_progress(p: Progress) -> None:
            task.progress = p
            task.stage = p.stage
            self._emit("progress", tid, p)

        def on_stage(s: str) -> None:
            task.stage = s
            self._emit("stage", tid, s)

        def on_log(level: str, msg: str) -> None:
            self._emit("log", tid, (level, msg))

        try:
            path = run_download(
                task.request, self.tools, on_progress, on_stage, on_log, task.cancel_event, verbose=self.verbose
            )
            task.result_path = path
            new_state = State.DONE
        except CancelledByUser:
            new_state = State.CANCELLED
        except Exception as e:  # noqa: BLE001 — every error must reach the GUI instead of killing the thread
            task.error = short_error(e)
            if not str(e).startswith("ERROR"):
                on_log("error", "".join(traceback.format_exception_only(type(e), e)).strip())
            new_state = State.ERROR
        removed = False
        with self._lock:
            if task.remove_when_done:
                self._tasks.pop(tid, None)
                removed = True
            elif tid in self._tasks:
                self._set_state(task, new_state)
        if removed:
            self._emit("removed", tid)
        self._pump()
