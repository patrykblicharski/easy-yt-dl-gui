"""Entry point: `python -m ytddlg` (GUI), `--check RESULT.json` or `--selftest OUT_DIR RESULT.json`."""

import sys


def ensure_streams() -> None:
    """In a windowed app (pythonw / .exe without a console) sys.stdout/stderr are None —
    any library write (e.g. a yt-dlp warning) would crash. Redirect them to a log file."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    from ytddlg.config import config_dir

    try:
        d = config_dir()
        d.mkdir(parents=True, exist_ok=True)
        stream = open(d / "ytddlg.log", "a", encoding="utf-8", buffering=1)
    except OSError:
        import os

        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def run() -> None:
    ensure_streams()
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        from ytddlg.selftest import main as selftest

        sys.exit(selftest(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        from ytddlg.selftest import check

        sys.exit(check(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--check-gui":
        from ytddlg.selftest import check_gui

        sys.exit(check_gui(sys.argv[2:]))
    from ytddlg.gui.app import main

    main()


if __name__ == "__main__":
    run()
