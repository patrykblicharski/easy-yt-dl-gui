"""Turns GUI choices into yt-dlp options.

Options are built as CLI arguments and passed through yt_dlp.parse_options, so the
library behaves exactly like a tested `yt-dlp ...` command, and the log can show the
equivalent command line.

Choices are stored as language-independent ids (e.g. "best", "1080", "mp3"); the GUI shows
translated labels via the *_label() helpers.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yt_dlp

from ..i18n import t
from .tools import Tools

MODE_VIDEO = "video"
MODE_AUDIO = "audio"

# video quality id -> max height (None = no limit)
VIDEO_QUALITIES: dict[str, int | None] = {
    "best": None,
    "2160": 2160,
    "1440": 1440,
    "1080": 1080,
    "720": 720,
    "480": 480,
}

CONTAINERS = ["MKV", "MP4"]

# audio format id == yt-dlp --audio-format value
AUDIO_FORMATS = ["best", "mp3", "m4a", "opus", "flac", "wav"]
LOSSY_AUDIO = {"mp3", "m4a", "opus"}
# Formats yt-dlp can embed a thumbnail into
THUMBNAIL_AUDIO = {"best", "mp3", "m4a", "opus", "flac"}

# audio quality id == yt-dlp --audio-quality value
AUDIO_QUALITIES = ["0", "320K", "256K", "192K", "128K"]

SB_OFF, SB_MARK, SB_REMOVE = "off", "mark", "remove"
SPONSORBLOCK_MODES = [SB_OFF, SB_MARK, SB_REMOVE]
SB_DEFAULT_CATEGORIES = "sponsor,selfpromo,interaction"
SB_ALL_CATEGORIES = [
    "sponsor", "intro", "outro", "selfpromo", "preview", "filler", "interaction", "music_offtopic", "hook",
]

COOKIE_BROWSERS = ["", "firefox", "chrome", "edge", "brave", "opera", "vivaldi", "chromium", "whale"]

DEFAULT_TEMPLATE = "%(title).150B [%(id)s].%(ext)s"
RATE_RE = re.compile(r"^\d+(\.\d+)?[KMG]?$", re.IGNORECASE)
LANGS_RE = re.compile(r"^[\w.*\-|^$]+(,[\w.*\-|^$]+)*$")

# Polish labels stored by versions <= 0.4 -> ids (settings.json and queue.json migration)
LEGACY_IDS = {
    "video_quality": {"Najlepsza": "best", "2160p (4K)": "2160", "1440p": "1440", "1080p": "1080",
                      "720p": "720", "480p": "480"},
    "audio_format": {"Oryginał (bez rekompresji)": "best", "MP3": "mp3", "M4A (AAC)": "m4a", "Opus": "opus",
                     "FLAC (bezstratny kontener)": "flac", "WAV": "wav"},
    "audio_quality": {"Najlepsza (VBR)": "0", "320 kb/s": "320K", "256 kb/s": "256K", "192 kb/s": "192K",
                      "128 kb/s": "128K"},
}


def migrate_ids(data: dict[str, Any]) -> dict[str, Any]:
    """Replaces legacy Polish labels with ids in a settings/request dict (in place)."""
    for key, mapping in LEGACY_IDS.items():
        if data.get(key) in mapping:
            data[key] = mapping[data[key]]
    return data


# --- translated labels ------------------------------------------------------------
def video_quality_label(qid: str) -> str:
    if qid == "best":
        return t("Best")
    if qid == "2160":
        return "2160p (4K)"
    return f"{qid}p"


def audio_format_label(fid: str) -> str:
    return {
        "best": t("Original (no re-encoding)"),
        "mp3": "MP3",
        "m4a": "M4A (AAC)",
        "opus": "Opus",
        "flac": t("FLAC (lossless container)"),
        "wav": "WAV",
    }.get(fid, fid)


def audio_quality_label(qid: str) -> str:
    return t("Best (VBR)") if qid == "0" else f"{qid[:-1]} kb/s"


def sponsorblock_label(mode: str) -> str:
    return {SB_OFF: t("Off"), SB_MARK: t("Mark as chapters"), SB_REMOVE: t("Cut out segments")}.get(mode, mode)


@dataclass
class NetOptions:
    """Network settings shared by probing and downloading."""

    cookies_browser: str = ""  # e.g. "firefox"
    cookies_file: str = ""  # cookies.txt file (Netscape format)
    rate_limit: str = ""  # e.g. "5M"; empty = no limit


@dataclass
class DownloadRequest:
    url: str
    out_dir: Path
    mode: str = MODE_VIDEO
    video_quality: str = "best"
    container: str = "MKV"
    compat: bool = False  # prefer H.264/AAC (players, TVs, editors)
    audio_format: str = "best"
    audio_quality: str = "0"
    template: str = DEFAULT_TEMPLATE
    title: str = ""  # only for display in the queue
    format_override: str = ""  # manually selected format, e.g. "137+251"
    subs: bool = False
    sub_langs: str = "pl,en"
    sub_auto: bool = False  # also auto-generated subtitles
    sub_embed: bool = True  # embed in the file instead of separate .srt files
    sponsorblock: str = SB_OFF
    sb_categories: str = SB_DEFAULT_CATEGORIES
    net: NetOptions = field(default_factory=NetOptions)
    extra_args: list[str] = field(default_factory=list)

    def label(self) -> str:
        if self.mode == MODE_AUDIO:
            fmt = self.audio_format
            text = t("Audio") + " · " + (t("original") if fmt == "best" else fmt.upper())
            if self.format_override:
                text += f" · f {self.format_override}"
        elif self.format_override:
            text = t("Video") + f" · f {self.format_override} · {self.container}"
        else:
            q = video_quality_label(self.video_quality).split(" ")[0]
            text = t("Video") + f" · {q} · {self.container}" + (" · H.264" if self.compat else "")
        if self.subs and self.mode == MODE_VIDEO:
            text += " · " + t("subtitles")
        if self.sponsorblock == SB_REMOVE:
            text += " · −SB"
        return text

    # --- serialization (queue persistence) -------------------------------
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["out_dir"] = str(self.out_dir)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DownloadRequest":
        known = {f.name for f in fields(cls)}
        data = migrate_ids({k: v for k, v in d.items() if k in known})
        net = data.pop("net", None) or {}
        net_known = {f.name for f in fields(NetOptions)}
        data["out_dir"] = Path(data.get("out_dir") or ".")
        return cls(net=NetOptions(**{k: v for k, v in net.items() if k in net_known}), **data)


def net_args(net: NetOptions | None, tools: Tools | None) -> list[str]:
    """Arguments shared by probing and downloading: tools, cookies, rate limit."""
    args: list[str] = ["--ignore-config"]
    if tools is not None:
        if tools.ffmpeg is not None:
            args += ["--ffmpeg-location", str(tools.ffmpeg.parent)]
        if tools.deno is not None:
            args += ["--js-runtimes", f"deno:{tools.deno}"]
    if net is not None:
        if net.cookies_file:
            args += ["--cookies", net.cookies_file]
        elif net.cookies_browser:
            args += ["--cookies-from-browser", net.cookies_browser]
        if net.rate_limit:
            if not RATE_RE.match(net.rate_limit):
                raise ValueError(t("Invalid speed limit: {value} (e.g. 5M, 800K)", value=net.rate_limit))
            args += ["--limit-rate", net.rate_limit]
    return args


def build_args(req: DownloadRequest, tools: Tools | None = None) -> list[str]:
    """yt-dlp CLI arguments (without the URL) for a request."""
    args = net_args(req.net, tools) + [
        "--no-playlist",
        "--windows-filenames",
        "--no-mtime",
        "--retries", "10",
        "--fragment-retries", "10",
        "-o", str(Path(req.out_dir) / req.template),
    ]

    if req.mode == MODE_AUDIO:
        fmt = req.audio_format
        if fmt not in AUDIO_FORMATS:
            raise ValueError(t("Unknown audio format: {value}", value=fmt))
        args += ["-f", req.format_override or "ba/b", "-x", "--audio-format", fmt]
        if fmt in LOSSY_AUDIO:
            args += ["--audio-quality", req.audio_quality if req.audio_quality in AUDIO_QUALITIES else "0"]
        args += ["--embed-metadata"]
        if fmt in THUMBNAIL_AUDIO:
            args += ["--embed-thumbnail"]
    elif req.mode == MODE_VIDEO:
        if req.container not in CONTAINERS:
            raise ValueError(t("Unknown container: {value}", value=req.container))
        if req.format_override:
            fmt_sel = req.format_override
        else:
            if req.video_quality not in VIDEO_QUALITIES:
                raise ValueError(t("Unknown video quality: {value}", value=req.video_quality))
            h = VIDEO_QUALITIES[req.video_quality]
            fmt_sel = "bv*+ba/b" if h is None else f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b"
        args += ["-f", fmt_sel, "--merge-output-format", req.container.lower()]
        if req.compat and not req.format_override:
            args += ["-S", "vcodec:h264,res,fps,acodec:aac"]
        args += ["--embed-metadata", "--embed-chapters"]
        if req.subs:
            langs = req.sub_langs.replace(" ", "")
            if not langs or not LANGS_RE.match(langs):
                raise ValueError(t("Invalid subtitle languages: {value} (e.g. pl,en)", value=repr(req.sub_langs)))
            args += ["--write-subs", "--sub-langs", langs]
            if req.sub_auto:
                args += ["--write-auto-subs"]
            if req.sub_embed:
                args += ["--embed-subs"]
            else:
                args += ["--convert-subs", "srt"]
    else:
        raise ValueError(t("Unknown mode: {value}", value=req.mode))

    if req.sponsorblock in (SB_MARK, SB_REMOVE):
        cats = req.sb_categories.replace(" ", "") or SB_DEFAULT_CATEGORIES
        unknown = set(cats.split(",")) - set(SB_ALL_CATEGORIES) - {"all", "default"}
        if unknown:
            raise ValueError(t("Unknown SponsorBlock categories: {value}", value=", ".join(sorted(unknown))))
        if req.sponsorblock == SB_MARK:
            args += ["--sponsorblock-mark", cats]
        else:
            args += ["--sponsorblock-remove", cats]
    elif req.sponsorblock != SB_OFF:
        raise ValueError(t("Unknown SponsorBlock mode: {value}", value=req.sponsorblock))

    args += list(req.extra_args)
    return args


def build_ydl_opts(req: DownloadRequest, tools: Tools | None = None) -> dict[str, Any]:
    """Options dict for yt_dlp.YoutubeDL (without hooks and logger)."""
    return dict(yt_dlp.parse_options(build_args(req, tools)).ydl_opts)


def probe_ydl_opts(net: NetOptions | None, tools: Tools | None, single_video: bool) -> dict[str, Any]:
    """Options for probing a link (no download, flat playlists)."""
    args = net_args(net, tools) + ["--flat-playlist", "--skip-download"]
    if single_video:
        args.append("--no-playlist")
    opts = dict(yt_dlp.parse_options(args).ydl_opts)
    opts.update({"quiet": True, "no_warnings": True, "noprogress": True})
    return opts


def command_line(req: DownloadRequest, tools: Tools | None = None) -> str:
    """Equivalent command line for the log / clipboard."""
    argv = ["yt-dlp", *build_args(req, tools), req.url]
    if sys.platform == "win32":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)
