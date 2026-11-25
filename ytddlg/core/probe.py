"""Link probing: video metadata or the list of playlist entries (no download)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import yt_dlp

from .options import NetOptions, probe_ydl_opts
from .tools import Tools


@dataclass
class Entry:
    url: str
    title: str
    duration: float | None = None
    index: int = 0


@dataclass
class FormatInfo:
    format_id: str
    ext: str
    kind: str  # "video" | "audio" | "av" (video+audio)
    height: int | None = None
    width: int | None = None
    fps: float | None = None
    vcodec: str = ""
    acodec: str = ""
    tbr: float | None = None  # kb/s
    abr: float | None = None
    asr: int | None = None
    filesize: int | None = None
    approx: bool = False
    note: str = ""
    protocol: str = ""
    dynamic_range: str = ""

    @property
    def resolution(self) -> str:
        if self.kind == "audio":
            return "tylko audio"
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return f"{self.height}p" if self.height else "?"


@dataclass
class ProbeResult:
    url: str
    kind: str  # "video" | "playlist"
    title: str
    uploader: str = ""
    duration: float | None = None
    thumbnail_url: str | None = None
    thumbnail_bytes: bytes | None = None
    max_height: int | None = None
    max_fps: float | None = None
    best_vcodec: str | None = None
    best_audio: str | None = None  # e.g. "opus 129k"
    subtitles: list[str] = field(default_factory=list)  # languages of manual (non-auto) subtitles
    auto_subtitles: bool = False
    entries: list[Entry] = field(default_factory=list)
    formats: list[FormatInfo] = field(default_factory=list)

    def summary(self) -> str:
        if self.kind == "playlist":
            parts = [f"Playlista · {len(self.entries)} pozycji"]
            if self.uploader:
                parts.append(self.uploader)
            return " · ".join(parts)
        parts = []
        if self.uploader:
            parts.append(self.uploader)
        if self.duration:
            parts.append(format_duration(self.duration))
        if self.max_height:
            fps = f"{int(self.max_fps)}" if self.max_fps and self.max_fps > 30 else ""
            parts.append(f"max {self.max_height}p{fps}")
        if self.best_audio:
            parts.append(f"audio {self.best_audio}")
        if self.subtitles:
            langs = ", ".join(self.subtitles[:6]) + ("…" if len(self.subtitles) > 6 else "")
            parts.append(f"napisy: {langs}")
        elif self.auto_subtitles:
            parts.append("napisy: tylko automatyczne")
        return " · ".join(parts)


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _pick_thumbnail(info: dict[str, Any]) -> str | None:
    thumbs = info.get("thumbnails") or []
    # Prefer ~320–700 px wide (small download, Pillow reads JPG/WebP)
    best = None
    for t in thumbs:
        if not t.get("url"):
            continue
        w = t.get("width") or 0
        if 300 <= w <= 700 and (best is None or w > (best.get("width") or 0)):
            best = t
    if best:
        return best["url"]
    return info.get("thumbnail") or (thumbs[-1]["url"] if thumbs else None)


def _codec(c: str | None) -> str:
    return "" if c in (None, "none") else str(c)


def _parse_formats(formats: list[dict[str, Any]]) -> list[FormatInfo]:
    out = []
    for f in formats:
        v, a = _codec(f.get("vcodec")), _codec(f.get("acodec"))
        if not v and not a:
            continue  # storyboards etc.
        if f.get("ext") == "mhtml":
            continue
        kind = "av" if v and a else ("video" if v else "audio")
        size = f.get("filesize")
        approx = False
        if not size and f.get("filesize_approx"):
            size, approx = f["filesize_approx"], True
        out.append(
            FormatInfo(
                format_id=str(f.get("format_id")),
                ext=f.get("ext") or "",
                kind=kind,
                height=f.get("height"),
                width=f.get("width"),
                fps=f.get("fps"),
                vcodec=v,
                acodec=a,
                tbr=f.get("tbr"),
                abr=f.get("abr"),
                asr=f.get("asr"),
                filesize=int(size) if size else None,
                approx=approx,
                note=f.get("format_note") or "",
                protocol=f.get("protocol") or "",
                dynamic_range=f.get("dynamic_range") or "",
            )
        )
    return out


def is_video_in_playlist(url: str) -> bool:
    """A watch?v=X&list=Y link is treated as a single video."""
    q = parse_qs(urlparse(url).query)
    return "v" in q and "list" in q


def probe(
    url: str,
    tools: Tools | None = None,
    net: NetOptions | None = None,
    logger: Any = None,
    fetch_thumbnail: bool = True,
) -> ProbeResult:
    opts = probe_ydl_opts(net, tools, single_video=is_video_in_playlist(url))
    opts.pop("ratelimit", None)  # the rate limit applies to downloads, not to probing
    if logger is not None:
        opts["logger"] = logger
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if info is None:
            raise RuntimeError("Nie udało się odczytać informacji o linku.")
        info = ydl.sanitize_info(info)

        if info.get("_type") == "playlist" or "entries" in info:
            entries = []
            for i, e in enumerate(info.get("entries") or [], start=1):
                if not e:
                    continue
                e_url = e.get("webpage_url") or e.get("url")
                if not e_url:
                    continue
                if not e_url.startswith("http") and e.get("ie_key") == "Youtube":
                    e_url = f"https://www.youtube.com/watch?v={e_url}"
                entries.append(
                    Entry(url=e_url, title=e.get("title") or e_url, duration=e.get("duration"), index=i)
                )
            result = ProbeResult(
                url=url,
                kind="playlist",
                title=info.get("title") or url,
                uploader=info.get("uploader") or info.get("channel") or "",
                thumbnail_url=_pick_thumbnail(info),
                entries=entries,
            )
        else:
            formats = _parse_formats(info.get("formats") or [])
            videos = [f for f in formats if f.kind != "audio" and f.height]
            audios = [f for f in formats if f.kind == "audio"]
            best_v = max(videos, key=lambda f: (f.height or 0, f.fps or 0), default=None)
            best_a = max(audios, key=lambda f: f.abr or 0, default=None)
            audio_desc = None
            if best_a:
                codec = best_a.acodec.split(".")[0]
                codec = {"mp4a": "aac"}.get(codec, codec)
                audio_desc = f"{codec} {int(best_a.abr)}k" if best_a.abr else codec
            subs = sorted(k for k in (info.get("subtitles") or {}) if k != "live_chat")
            result = ProbeResult(
                url=info.get("webpage_url") or url,
                kind="video",
                title=info.get("title") or url,
                uploader=info.get("uploader") or info.get("channel") or "",
                duration=info.get("duration"),
                thumbnail_url=_pick_thumbnail(info),
                max_height=best_v.height if best_v else None,
                max_fps=best_v.fps if best_v else None,
                best_vcodec=best_v.vcodec.split(".")[0] if best_v else None,
                best_audio=audio_desc,
                subtitles=subs,
                auto_subtitles=bool(info.get("automatic_captions")),
                formats=formats,
            )

        if fetch_thumbnail and result.thumbnail_url:
            try:
                with ydl.urlopen(result.thumbnail_url) as resp:
                    result.thumbnail_bytes = resp.read()
            except Exception:
                result.thumbnail_bytes = None
    return result
