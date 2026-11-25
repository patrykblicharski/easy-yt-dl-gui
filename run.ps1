# Starts Easy yt-dl-gui from source using the local .venv (no console window)
$root = $PSScriptRoot
$pyw  = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pyw)) {
    Write-Host 'No .venv found - run .\setup_env.ps1 first'
    exit 1
}
Start-Process -FilePath $pyw -ArgumentList '-m', 'ytddlg' -WorkingDirectory $root
