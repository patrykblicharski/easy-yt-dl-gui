# Third-party components

The Easy yt-dl-gui source code is MIT-licensed (see `LICENSE`). The release packages additionally
bundle the following programs and libraries, each under its own license.

| Component | License | Source |
|---|---|---|
| FFmpeg / FFprobe (static builds fetched by the `static-ffmpeg` package) | GPL v3 | https://ffmpeg.org · https://www.gyan.dev/ffmpeg/builds/ · https://johnvansickle.com/ffmpeg/ |
| Deno | MIT | https://github.com/denoland/deno |
| yt-dlp | Unlicense | https://github.com/yt-dlp/yt-dlp |
| yt-dlp-ejs | Unlicense | https://github.com/yt-dlp/ejs |
| CustomTkinter | MIT | https://github.com/TomSchimansky/CustomTkinter |
| Pillow | MIT-CMU (HPND) | https://github.com/python-pillow/Pillow |
| curl_cffi | MIT | https://github.com/lexiforest/curl_cffi |
| mutagen | GPL v2+ | https://github.com/quodlibet/mutagen |
| pycryptodomex | BSD / Public Domain | https://github.com/Legrandin/pycryptodome |
| Brotli, certifi, requests, urllib3, websockets | MIT / MPL-2.0 / Apache-2.0 / BSD | PyPI |
| Python and Tcl/Tk (bundled runtime) | PSF License / Tcl license | https://www.python.org · https://www.tcl.tk |

FFmpeg and mutagen are GPL-licensed; their source code is available at the addresses above.
The bundled FFmpeg binaries are unmodified upstream static builds.
