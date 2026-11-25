from pathlib import Path

import pytest

from ytddlg.core.options import (
    AUDIO_FORMATS,
    MODE_AUDIO,
    MODE_VIDEO,
    SB_MARK,
    SB_REMOVE,
    VIDEO_QUALITIES,
    DownloadRequest,
    NetOptions,
    build_args,
    build_ydl_opts,
    probe_ydl_opts,
)
from ytddlg.core.tools import detect_tools

OUT = Path("C:/tmp/out")


def pp_keys(opts):
    return [pp["key"] for pp in opts.get("postprocessors", [])]


def test_video_best_mkv():
    opts = build_ydl_opts(DownloadRequest("u", OUT))
    assert opts["format"] == "bv*+ba/b"
    assert opts["merge_output_format"] == "mkv"
    assert opts["noplaylist"] is True
    assert "FFmpegMetadata" in pp_keys(opts)


def test_video_height_limit():
    opts = build_ydl_opts(DownloadRequest("u", OUT, video_quality="1080"))
    assert opts["format"].startswith("bv*[height<=1080]+ba/b[height<=1080]")


def test_video_compat_mp4():
    opts = build_ydl_opts(DownloadRequest("u", OUT, container="MP4", compat=True))
    assert opts["merge_output_format"] == "mp4"
    assert opts["format_sort"][0] == "vcodec:h264"


def test_audio_original_no_quality():
    args = build_args(DownloadRequest("u", OUT, mode=MODE_AUDIO))
    assert "--audio-quality" not in args
    opts = build_ydl_opts(DownloadRequest("u", OUT, mode=MODE_AUDIO))
    extract = next(pp for pp in opts["postprocessors"] if pp["key"] == "FFmpegExtractAudio")
    assert extract["preferredcodec"] == "best"
    assert "EmbedThumbnail" in pp_keys(opts)
    assert opts["writethumbnail"] is True


def test_audio_mp3_320():
    req = DownloadRequest("u", OUT, mode=MODE_AUDIO, audio_format="mp3", audio_quality="320K")
    opts = build_ydl_opts(req)
    extract = next(pp for pp in opts["postprocessors"] if pp["key"] == "FFmpegExtractAudio")
    assert extract["preferredcodec"] == "mp3"
    assert extract["preferredquality"] == "320"  # yt-dlp normalizes "320K" -> "320"


def test_wav_has_no_thumbnail():
    opts = build_ydl_opts(DownloadRequest("u", OUT, mode=MODE_AUDIO, audio_format="wav"))
    assert "EmbedThumbnail" not in pp_keys(opts)


@pytest.mark.parametrize("q", list(VIDEO_QUALITIES))
@pytest.mark.parametrize("c", ["MKV", "MP4"])
def test_all_video_presets_parse(q, c):
    build_ydl_opts(DownloadRequest("u", OUT, mode=MODE_VIDEO, video_quality=q, container=c))


@pytest.mark.parametrize("f", list(AUDIO_FORMATS))
def test_all_audio_presets_parse(f):
    build_ydl_opts(DownloadRequest("u", OUT, mode=MODE_AUDIO, audio_format=f))


def test_tools_paths_passed():
    tools = detect_tools()
    assert tools.ok, f"brakuje: {tools.missing}"
    opts = build_ydl_opts(DownloadRequest("u", OUT), tools)
    assert opts["ffmpeg_location"] == str(tools.ffmpeg.parent)
    assert opts["js_runtimes"] == {"deno": {"path": str(tools.deno)}}


def test_invalid_values():
    with pytest.raises(ValueError):
        build_args(DownloadRequest("u", OUT, video_quality="8K"))
    with pytest.raises(ValueError):
        build_args(DownloadRequest("u", OUT, mode="x"))


# --- version 2 -------------------------------------------------------------------
def test_format_override_video():
    opts = build_ydl_opts(DownloadRequest("u", OUT, format_override="137+251", compat=True))
    assert opts["format"] == "137+251"
    assert "format_sort" not in opts or not opts["format_sort"]


def test_format_override_audio():
    opts = build_ydl_opts(DownloadRequest("u", OUT, mode=MODE_AUDIO, format_override="251"))
    assert opts["format"] == "251"
    assert "FFmpegExtractAudio" in pp_keys(opts)


def test_subtitles_embed():
    opts = build_ydl_opts(DownloadRequest("u", OUT, subs=True, sub_langs="pl, en", sub_auto=True))
    assert opts["writesubtitles"] is True
    assert opts["writeautomaticsub"] is True
    assert opts["subtitleslangs"] == ["pl", "en"]
    assert "FFmpegEmbedSubtitle" in pp_keys(opts)


def test_subtitles_separate_srt():
    opts = build_ydl_opts(DownloadRequest("u", OUT, subs=True, sub_embed=False))
    assert "FFmpegEmbedSubtitle" not in pp_keys(opts)
    conv = next(pp for pp in opts["postprocessors"] if pp["key"] == "FFmpegSubtitlesConvertor")
    assert conv["format"] == "srt"


def test_subtitles_ignored_for_audio():
    args = build_args(DownloadRequest("u", OUT, mode=MODE_AUDIO, subs=True))
    assert "--write-subs" not in args


def test_bad_sub_langs():
    with pytest.raises(ValueError):
        build_args(DownloadRequest("u", OUT, subs=True, sub_langs="pl;en"))


def test_sponsorblock_remove_and_mark():
    opts = build_ydl_opts(DownloadRequest("u", OUT, sponsorblock=SB_REMOVE, sb_categories="sponsor,intro"))
    assert "SponsorBlock" in pp_keys(opts)
    mc = next(pp for pp in opts["postprocessors"] if pp["key"] == "ModifyChapters")
    assert set(mc["remove_sponsor_segments"]) == {"sponsor", "intro"}
    opts = build_ydl_opts(DownloadRequest("u", OUT, mode=MODE_AUDIO, sponsorblock=SB_MARK))
    assert "SponsorBlock" in pp_keys(opts)


def test_sponsorblock_bad_category():
    with pytest.raises(ValueError):
        build_args(DownloadRequest("u", OUT, sponsorblock=SB_REMOVE, sb_categories="sponsor,reklama"))


def test_net_options():
    net = NetOptions(cookies_browser="firefox", rate_limit="5M")
    opts = build_ydl_opts(DownloadRequest("u", OUT, net=net))
    assert opts["cookiesfrombrowser"][0] == "firefox"
    assert opts["ratelimit"] == 5 * 1024 * 1024
    opts = build_ydl_opts(DownloadRequest("u", OUT, net=NetOptions(cookies_browser="firefox", cookies_file="c.txt")))
    assert opts["cookiefile"] == "c.txt"
    assert not opts.get("cookiesfrombrowser")
    with pytest.raises(ValueError):
        build_args(DownloadRequest("u", OUT, net=NetOptions(rate_limit="szybko")))


def test_probe_opts():
    opts = probe_ydl_opts(NetOptions(cookies_browser="firefox"), None, single_video=True)
    assert opts["extract_flat"] == "in_playlist"
    assert opts["noplaylist"] is True
    assert opts["skip_download"] is True
    assert opts["cookiesfrombrowser"][0] == "firefox"


def test_request_roundtrip():
    req = DownloadRequest(
        "u", OUT, mode=MODE_AUDIO, title="Tytuł ąę", subs=True, sponsorblock=SB_MARK,
        net=NetOptions(cookies_browser="firefox"), format_override="251",
    )
    back = DownloadRequest.from_dict(req.to_dict())
    assert back == req


def test_label():
    assert "subtitles" in DownloadRequest("u", OUT, subs=True).label()
    assert "f 137+251" in DownloadRequest("u", OUT, format_override="137+251").label()
