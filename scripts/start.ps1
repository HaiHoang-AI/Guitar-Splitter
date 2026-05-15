$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$LocalFfmpegBin = Join-Path $Root "tools\ffmpeg\bin"
$LocalTorchHome = Join-Path $Root "tools\model-cache\torch"
if (Test-Path $LocalFfmpegBin) {
  $env:PATH = "$LocalFfmpegBin;$env:PATH"
}
$env:TORCH_HOME = $LocalTorchHome

if (Test-Path ".venv\Scripts\python.exe") {
  $Python = ".\.venv\Scripts\python.exe"
} elseif (Test-Path "C:\Users\ADMIN\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe") {
  $Python = "C:\Users\ADMIN\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
} else {
  $Python = "python"
}

& $Python app.py
