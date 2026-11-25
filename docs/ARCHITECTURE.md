# Architecture

Easy yt-dl-gui is a thin desktop front-end over [yt-dlp](https://github.com/yt-dlp/yt-dlp),
written in Python with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

```
ytddlg/
├─ __main__.py          entry point: GUI, --check, --selftest
├─ config.py            settings (%APPDATA%\ytddlg or ~/.config/ytddlg; YTDDLG_CONFIG_DIR overrides)
├─ selftest.py          headless checks for the bundled app
├─ core/                no GUI imports — testable and usable from scripts
│  ├─ tools.py          finds ffmpeg / ffprobe / deno (bundle dir → venv → PATH)
│  ├─ options.py        DownloadRequest → yt-dlp CLI args → yt_dlp.parse_options → options dict
│  ├─ probe.py          extract_info(download=False): metadata, formats, playlist entries
│  ├─ downloader.py     one download: progress/stage hooks, cancellation, logger
│  ├─ queue.py          task queue: states, parallelism limit, events, persistence
│  └─ files.py          Recycle Bin / Trash, companion files
└─ gui/
   ├─ app.py            main window
   ├─ queue_view.py     queue table, action bar, per-row actions, context menu
   ├─ dialogs.py        playlist picker, format picker, settings
   ├─ tree.py           ttk.Treeview styled like CustomTkinter (theme, DPI, row colours)
   ├─ theme.py          colour palette
   ├─ notify.py         finish notification, YouTube URL detection
   ├─ resources.py      icon / logo loading
   └─ fmt.py            human-readable sizes, speeds and durations
```

## Key decisions

**yt-dlp as a library, configured through its own CLI parser.** `core/options.py` builds a list of
ordinary `yt-dlp` arguments and passes it through `yt_dlp.parse_options`. The library therefore behaves
exactly like the equivalent command line, which is also written to the log and can be copied from the
queue's context menu — handy for debugging and bug reports.

**Bundled tools.** ffmpeg/ffprobe (merging, audio extraction, thumbnails) and Deno (yt-dlp's JavaScript
runtime for YouTube's player challenges — without it only low qualities are available) are shipped next to
the app and passed to yt-dlp explicitly via `--ffmpeg-location` and `--js-runtimes`.

**Threads never touch Tk.** Workers publish events (`added`, `state`, `progress`, `stage`, `log`, `removed`)
to a `queue.Queue`. The window drains it every 100 ms and refreshes each changed row once per tick.

**Adding ≠ starting.** New tasks are `IDLE` until started (button, Enter, double-click), unless auto-start
is enabled. Unfinished tasks are saved to `queue.json` and restored as `IDLE` on the next launch.

**Treeview queue.** A styled `ttk.Treeview` instead of rows of CTk widgets keeps the list compact and fast
with hundreds of entries. Row actions are text segments in the last column, hit-tested by measuring the
font. In Tk 8.6.10+ tag colours override the selection colour, so selection is an extra `sel` tag
configured last.

## Testing

```
python -m pytest -q tests                      # offline (options, queue, helpers)
YTDDLG_NETWORK=1 python -m pytest -q tests     # + real YouTube: probe, downloads, cancel
```

Tests always use a temporary settings folder (`tests/conftest.py`).
The bundled app has two headless modes used by the build scripts and CI:

```
"Easy yt-dl-gui.exe" --check result.json                 # tools bundled and runnable (offline)
"Easy yt-dl-gui.exe" --selftest out_dir result.json      # probe + download a short video and an MP3
```
