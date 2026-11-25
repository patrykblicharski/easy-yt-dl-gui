"""Headless self-tests for the bundled app (Windows .exe / Linux).

  --check     <result.json>                   offline: are the tools bundled and runnable
  --check-gui <result.json>                   open and close the main window (needs a display)
  --selftest  <out_dir> <result.json> [URL]   full test: probe + download a video and an MP3
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import traceback
from pathlib import Path

DEFAULT_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # 19 s


def _write(result_file: Path, result: dict) -> None:
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def check(argv: list[str]) -> int:
    """Offline check — used in CI, where YouTube often blocks datacenter IPs."""
    if not argv:
        print(__doc__)
        return 2
    result_file = Path(argv[0])
    result: dict = {"ok": False, "frozen": bool(getattr(sys, "frozen", False)), "platform": sys.platform}
    try:
        import yt_dlp.version

        from .core.options import DownloadRequest, build_ydl_opts
        from .core.tools import detect_tools

        tools = detect_tools()
        result["yt_dlp"] = yt_dlp.version.__version__
        result["tools"] = {}
        for name, flag in (("ffmpeg", "-version"), ("ffprobe", "-version"), ("deno", "--version")):
            path = getattr(tools, name)
            if path is None:
                raise RuntimeError(f"{name} is not bundled")
            out = subprocess.run([str(path), flag], capture_output=True, text=True, timeout=60)
            first = (out.stdout or out.stderr).splitlines()[0] if (out.stdout or out.stderr) else ""
            if out.returncode != 0:
                raise RuntimeError(f"{name} does not run (exit {out.returncode}): {first}")
            result["tools"][name] = {"path": str(path), "version": first[:80]}
        opts = build_ydl_opts(DownloadRequest(DEFAULT_URL, Path(".")), tools)
        result["js_runtimes"] = list(opts.get("js_runtimes", {}))
        import yt_dlp_ejs  # noqa: F401 — the JS challenge solver scripts must be bundled

        # Modules loaded dynamically by the GUI (missed by PyInstaller on Linux in 0.4.0)
        import PIL._tkinter_finder  # noqa: F401
        import PIL.ImageTk  # noqa: F401
        import customtkinter  # noqa: F401

        result["ok"] = True
    except Exception as e:  # noqa: BLE001
        result["error"] = "".join(traceback.format_exception(e))[-3000:]
    _write(result_file, result)
    return 0 if result["ok"] else 1


def check_gui(argv: list[str]) -> int:
    """Opens the real main window for a moment and closes it (needs a display; use xvfb-run in CI).

    Any exception — also one raised inside a Tk callback — fails the check.
    """
    if not argv:
        print(__doc__)
        return 2
    result_file = Path(argv[0])
    result: dict = {"ok": False, "frozen": bool(getattr(sys, "frozen", False)), "platform": sys.platform}
    errors: list[str] = []
    try:
        from .config import Settings
        from .gui.app import App

        app = App(settings=Settings(auto_paste=False, restore_queue=False, watch_clipboard=False), restore=False)

        def report(exc, val, tb):
            errors.append("".join(traceback.format_exception(exc, val, tb))[-3000:])

        app.report_callback_exception = report

        def finish():
            try:
                app.update()
                result["window"] = {"title": app.title(), "width": app.winfo_width(), "height": app.winfo_height()}
                from .gui.dialogs import SettingsDialog

                dlg = SettingsDialog(app, app.settings, lambda: None)  # exercises the dialog code path too
                app.update()
                dlg.close()
            except Exception:  # noqa: BLE001
                errors.append(traceback.format_exc()[-3000:])
            finally:
                for job in (getattr(app, "_poll_id", None), getattr(app, "_clip_job", None)):
                    try:
                        app.after_cancel(job)
                    except Exception:  # noqa: BLE001
                        pass
                app.destroy()

        app.after(1500, finish)
        app.mainloop()
        if errors:
            result["error"] = "\n\n".join(errors)
        else:
            result["ok"] = True
    except Exception as e:  # noqa: BLE001
        result["error"] = "".join(traceback.format_exception(e))[-3000:]
    _write(result_file, result)
    return 0 if result["ok"] else 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    out_dir, result_file = Path(argv[0]), Path(argv[1])
    url = argv[2] if len(argv) > 2 else DEFAULT_URL
    result: dict = {"ok": False, "frozen": bool(getattr(sys, "frozen", False)), "platform": sys.platform}
    try:
        import yt_dlp.version

        from .core.downloader import run_download
        from .core.options import MODE_AUDIO, DownloadRequest
        from .core.probe import probe
        from .core.tools import detect_tools

        tools = detect_tools()
        result["yt_dlp"] = yt_dlp.version.__version__
        result["tools"] = {k: str(getattr(tools, k)) for k in ("ffmpeg", "ffprobe", "deno")}
        if not tools.ok:
            raise RuntimeError(f"missing tools:{tools.missing}")

        info = probe(url, tools)
        result["probe"] = {"title": info.title, "max_height": info.max_height, "formats": len(info.formats)}

        logs: list[str] = []

        def log(level, msg):
            logs.append(f"{level}: {msg}")

        files = []
        for req in (
            DownloadRequest(url, out_dir),
            DownloadRequest(url, out_dir, mode=MODE_AUDIO, audio_format="mp3"),
        ):
            p = run_download(req, tools, lambda p: None, lambda s: None, log, threading.Event())
            files.append({"path": str(p), "size": p.stat().st_size if p and p.exists() else 0})
        result["files"] = files
        result["log_tail"] = logs[-8:]
        result["ok"] = all(f["size"] > 0 for f in files)
    except Exception as e:  # noqa: BLE001
        result["error"] = "".join(traceback.format_exception(e))[-3000:]
    _write(result_file, result)
    return 0 if result["ok"] else 1
