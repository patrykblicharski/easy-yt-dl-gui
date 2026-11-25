"""Runs a single download with progress reporting and cancellation."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yt_dlp
from yt_dlp.utils import DownloadCancelled, DownloadError

from .options import DownloadRequest, build_ydl_opts
from .tools import Tools


@dataclass
class Progress:
    fraction: float | None  # 0..1 or None (unknown size)
    downloaded: int
    total: int | None
    speed: float | None  # B/s
    eta: int | None  # s
    stage: str  # stage description, e.g. "Obraz 1/2"


class CancelledByUser(Exception):
    pass


class LogAdapter:
    """yt-dlp logger that forwards lines to a callback (level, text)."""

    def __init__(self, emit: Callable[[str, str], None], verbose: bool = False):
        self._emit = emit
        self._verbose = verbose

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            if self._verbose:
                self._emit("debug", msg)
        else:
            self._emit("info", msg)

    def info(self, msg: str) -> None:
        self._emit("info", msg)

    def warning(self, msg: str) -> None:
        self._emit("warning", msg)

    def error(self, msg: str) -> None:
        self._emit("error", msg)


class _ProgressTracker:
    """Combines the progress of multiple streams (video + audio) into a single bar."""

    def __init__(self) -> None:
        self.files: dict[str, tuple[int, int | None]] = {}
        self.expected_total: int | None = None
        self.n_streams = 1

    def update(self, d: dict[str, Any]) -> Progress:
        info = d.get("info_dict") or {}
        req = info.get("requested_formats")
        if req and self.expected_total is None:
            self.n_streams = len(req)
            sizes = [f.get("filesize") or f.get("filesize_approx") for f in req]
            if all(sizes):
                self.expected_total = int(sum(sizes))
        fname = d.get("filename") or d.get("tmpfilename") or "?"
        done = int(d.get("downloaded_bytes") or 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        total = int(total) if total else None
        if d.get("status") == "finished" and total is None:
            total = done
        self.files[fname] = (done, total)

        sum_done = sum(v[0] for v in self.files.values())
        sum_total = sum(v[1] for v in self.files.values() if v[1]) or None
        denom: int | None
        if self.n_streams > 1 and self.expected_total:
            denom = max(self.expected_total, sum_total or 0)
            fraction: float | None = sum_done / denom
        elif self.n_streams > 1:
            # Size of the next stream is unknown: each stream is an equal share of the bar
            idx = list(self.files).index(fname)
            part = done / total if total else 0.0
            denom = sum_total
            fraction = (idx + part) / self.n_streams
        else:
            denom = total
            fraction = done / total if total else None
        if fraction is not None:
            fraction = max(0.0, min(1.0, fraction))

        vcodec = info.get("vcodec")
        kind = "Dźwięk" if vcodec in (None, "none") else "Obraz"
        if self.n_streams > 1:
            stage = f"{kind} {min(len(self.files), self.n_streams)}/{self.n_streams}"
        else:
            stage = "Pobieranie"
        return Progress(
            fraction=fraction,
            downloaded=sum_done,
            total=denom,
            speed=d.get("speed"),
            eta=int(d["eta"]) if d.get("eta") is not None else None,
            stage=stage,
        )


# Keys are PostProcessor.pp_key() (class name without "PP" and without the "FFmpeg" prefix)
PP_NAMES = {
    "Merger": "Scalanie",
    "ExtractAudio": "Wyodrębnianie audio",
    "Metadata": "Metadane",
    "EmbedThumbnail": "Okładka",
    "ThumbnailsConvertor": "Okładka",
    "EmbedSubtitle": "Osadzanie napisów",
    "SubtitlesConvertor": "Konwersja napisów",
    "SponsorBlock": "SponsorBlock",
    "ModifyChapters": "Wycinanie segmentów",
    "FixupM3u8": "Naprawa kontenera",
    "FixupM4a": "Naprawa kontenera",
    "FixupStretched": "Naprawa proporcji",
    "FixupDuplicateMoov": "Naprawa kontenera",
    "FixupTimestamp": "Naprawa znaczników",
    "MoveFiles": "Przenoszenie",
    "MoveFilesAfterDownload": "Przenoszenie",
}


def run_download(
    req: DownloadRequest,
    tools: Tools | None,
    on_progress: Callable[[Progress], None],
    on_stage: Callable[[str], None],
    on_log: Callable[[str, str], None],
    cancel_event: threading.Event,
    verbose: bool = False,
) -> Path | None:
    """Downloads one video and returns the path of the finished file.

    Raises CancelledByUser when cancelled and DownloadError on yt-dlp errors.
    """
    tracker = _ProgressTracker()
    final_path: list[str] = []

    def progress_hook(d: dict[str, Any]) -> None:
        if cancel_event.is_set():
            raise DownloadCancelled("Anulowano przez użytkownika")
        if d.get("status") in ("downloading", "finished"):
            on_progress(tracker.update(d))

    def pp_hook(d: dict[str, Any]) -> None:
        name = d.get("postprocessor") or ""
        if d.get("status") == "started":
            on_stage(PP_NAMES.get(name, name or "Przetwarzanie"))
        elif d.get("status") == "finished":
            fp = (d.get("info_dict") or {}).get("filepath")
            if fp:
                final_path.append(fp)
        if cancel_event.is_set():
            raise DownloadCancelled("Anulowano przez użytkownika")

    opts = build_ydl_opts(req, tools)
    opts.update(
        {
            "logger": LogAdapter(on_log, verbose=verbose),
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [pp_hook],
            "noprogress": True,
            "quiet": False,
            "verbose": verbose,
        }
    )
    Path(req.out_dir).mkdir(parents=True, exist_ok=True)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            on_stage("Analiza")
            info = ydl.extract_info(req.url, download=True)
    except DownloadCancelled as e:
        raise CancelledByUser(str(e)) from e
    except DownloadError:
        if cancel_event.is_set():
            raise CancelledByUser("Anulowano przez użytkownika")
        raise

    if final_path:
        return Path(final_path[-1])
    if info:
        for rd in info.get("requested_downloads") or []:
            if rd.get("filepath"):
                return Path(rd["filepath"])
    return None
