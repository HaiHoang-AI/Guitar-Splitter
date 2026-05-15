$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ToolsDir = Join-Path $Root "tools"
$FfmpegDir = Join-Path $ToolsDir "ffmpeg"
$FfmpegExe = Join-Path $FfmpegDir "bin\ffmpeg.exe"
$FfmpegArchive = Join-Path $ToolsDir "ffmpeg-release-full-shared.7z"
$FfmpegExtract = Join-Path $ToolsDir "ffmpeg-extract"
$FfmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full-shared.7z"

New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

$PythonCandidates = @(
  "C:\Users\ADMIN\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
  "py",
  "python"
)

$Python = $null
foreach ($Candidate in $PythonCandidates) {
  try {
    $Version = & $Candidate --version 2>$null
    if ($LASTEXITCODE -eq 0 -and $Version) {
      $Python = $Candidate
      break
    }
  } catch {
  }
}

if (-not $Python) {
  throw "Python was not found. Install Python 3.10+ or run this inside Codex where the bundled Python path exists."
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -and (-not (Test-Path $FfmpegExe) -or -not (Get-ChildItem -Path (Split-Path -Parent $FfmpegExe) -Filter "avcodec*.dll" -ErrorAction SilentlyContinue))) {
  Write-Host "Downloading FFmpeg portable build..."
  Invoke-WebRequest -Uri $FfmpegUrl -OutFile $FfmpegArchive

  if (Test-Path $FfmpegExtract) {
    Remove-Item -LiteralPath $FfmpegExtract -Recurse -Force
  }
  if (Test-Path $FfmpegDir) {
    Remove-Item -LiteralPath $FfmpegDir -Recurse -Force
  }

  New-Item -ItemType Directory -Force -Path $FfmpegExtract | Out-Null
  tar -xf $FfmpegArchive -C $FfmpegExtract
  $FoundFfmpeg = Get-ChildItem -LiteralPath $FfmpegExtract -Recurse -Filter ffmpeg.exe | Select-Object -First 1
  if (-not $FoundFfmpeg) {
    throw "FFmpeg download was extracted, but ffmpeg.exe was not found."
  }

  $BuildRoot = Split-Path -Parent (Split-Path -Parent $FoundFfmpeg.FullName)
  Move-Item -LiteralPath $BuildRoot -Destination $FfmpegDir
  Remove-Item -LiteralPath $FfmpegExtract -Recurse -Force
  Remove-Item -LiteralPath $FfmpegArchive -Force
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  & $Python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete."
if (Test-Path $FfmpegExe) {
  Write-Host "FFmpeg portable is installed at: $FfmpegExe"
} else {
  Write-Host "Using FFmpeg from PATH."
}
Write-Host "Then run: .\scripts\start.ps1"
