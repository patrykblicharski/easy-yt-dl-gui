# Builds dist\Easy yt-dl-gui\Easy yt-dl-gui.exe (one-folder build bundling ffmpeg, ffprobe and deno),
# runs the offline package check and packs it into release\Easy-yt-dl-gui-v<version>-win64.zip (+ .sha256).
# Usage:  powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 [-SelfTest] [-NoZip]
#   -SelfTest  also run the full self-test (probes and downloads a short YouTube video)
param([switch]$SelfTest, [switch]$NoZip)
$ErrorActionPreference = 'Stop'
$root    = $PSScriptRoot
$py      = Join-Path $root '.venv\Scripts\python.exe'
$appName = 'Easy yt-dl-gui'
$distDir = Join-Path $root "dist\$appName"
$exe     = Join-Path $distDir "$appName.exe"

$version = (& $py -c "import sys; sys.path.insert(0, r'$root'); import ytddlg; print(ytddlg.__version__)").Trim()
Write-Host "Version: $version"

& $py -m pip install --quiet --upgrade pyinstaller
& $py -m PyInstaller --noconfirm --clean (Join-Path $root 'ytddlg.spec') `
    --distpath (Join-Path $root 'dist') --workpath (Join-Path $root 'build')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

Copy-Item (Join-Path $root 'LICENSE') (Join-Path $distDir 'LICENSE.txt') -Force
Copy-Item (Join-Path $root 'THIRD_PARTY_NOTICES.md') (Join-Path $distDir 'THIRD_PARTY_NOTICES.md') -Force

$size = (Get-ChildItem $distDir -Recurse | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("Built: {0}  ({1:N0} MB)" -f $exe, $size)

# Run the bundled app headless; settings go to a temp folder, never to the real %APPDATA%
$tmp = Join-Path $env:TEMP 'ytddlg_build_check'
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
$env:YTDDLG_CONFIG_DIR = Join-Path $tmp 'config'
try {
    $p = Start-Process -FilePath $exe -ArgumentList '--check', "`"$tmp\check.json`"" -Wait -PassThru
    if ($p.ExitCode -ne 0) { Get-Content (Join-Path $tmp 'check.json'); throw "Package check failed ($($p.ExitCode))" }
    Write-Host 'Package check: OK'

    $p = Start-Process -FilePath $exe -ArgumentList '--check-gui', "`"$tmp\check_gui.json`"" -Wait -PassThru
    if ($p.ExitCode -ne 0) { Get-Content (Join-Path $tmp 'check_gui.json'); throw "GUI check failed ($($p.ExitCode))" }
    Write-Host 'GUI check: OK'

    if ($SelfTest) {
        $p = Start-Process -FilePath $exe -ArgumentList '--selftest', "`"$tmp\out`"", "`"$tmp\result.json`"" -Wait -PassThru
        Get-Content (Join-Path $tmp 'result.json')
        if ($p.ExitCode -ne 0) { throw "Self-test failed ($($p.ExitCode))" }
        Write-Host 'Self-test: OK'
    }
} finally {
    Remove-Item Env:\YTDDLG_CONFIG_DIR -ErrorAction SilentlyContinue
}

if (-not $NoZip) {
    $relDir = Join-Path $root 'release'
    New-Item -ItemType Directory -Force $relDir | Out-Null
    $zip = Join-Path $relDir "Easy-yt-dl-gui-v$version-win64.zip"
    Remove-Item $zip, "$zip.sha256" -Force -ErrorAction SilentlyContinue
    $sevenZip = Get-Command 7z -ErrorAction SilentlyContinue
    if ($sevenZip) {
        & $sevenZip.Source a -tzip -mx=7 $zip $distDir | Out-Null
    } else {
        Compress-Archive -Path $distDir -DestinationPath $zip -CompressionLevel Optimal
    }
    $hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    "$hash  $(Split-Path $zip -Leaf)" | Set-Content -Encoding ascii "$zip.sha256"
    Write-Host ("Package: {0}  ({1:N0} MB)  sha256 {2}" -f $zip, ((Get-Item $zip).Length / 1MB), $hash)
}
