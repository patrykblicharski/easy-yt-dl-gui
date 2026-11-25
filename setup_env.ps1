# Sets up the development environment on Windows: .venv + yt-dlp + ffmpeg/ffprobe + deno (all inside .venv)
# Usage:  powershell -ExecutionPolicy Bypass -File .\setup_env.ps1
$ErrorActionPreference = 'Stop'
$root    = $PSScriptRoot
$venv    = Join-Path $root '.venv'
$scripts = Join-Path $venv 'Scripts'
$py      = Join-Path $scripts 'python.exe'

if (-not (Test-Path $py)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 -m venv $venv } else { python -m venv $venv }
}
& $py -m pip install --upgrade pip
& $py -m pip install --upgrade -r (Join-Path $root 'requirements.txt')

# Fetch static ffmpeg/ffprobe builds and copy them into .venv\Scripts (on PATH once the venv is active).
# The copy happens in Python: on the first run static_ffmpeg prints download progress to stdout,
# so its output cannot be parsed as a list of paths.
& $py -c "import shutil, sys, static_ffmpeg.run as r; [shutil.copy2(p, sys.argv[1]) for p in r.get_or_fetch_platform_executables_else_raise()]" $scripts
if ($LASTEXITCODE -ne 0) { throw "Fetching ffmpeg/ffprobe failed ($LASTEXITCODE)" }
foreach ($tool in 'ffmpeg.exe', 'ffprobe.exe') {
    if (-not (Test-Path (Join-Path $scripts $tool))) { throw "$tool was not copied to $scripts" }
}

$env:PATH = "$scripts;$env:PATH"
Write-Host "yt-dlp : $(yt-dlp --version)"
Write-Host "ffmpeg : $((ffmpeg -hide_banner -version | Select-Object -First 1))"
Write-Host "deno   : $((deno --version | Select-Object -First 1))"
