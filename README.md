# Guitar Splitter

Local web app for separating guitar from a song or instrumental track.

The app accepts common audio/video formats, runs a local Demucs separation job,
and returns two WAV outputs:

- `guitar.wav`: isolated guitar stem
- `no_guitar.wav`: mix with guitar removed

It is designed to run locally on Windows with no cloud processing.

## Features

- Browser UI for upload, job progress, preview, and download
- Supports MP3, WAV, FLAC, M4A, AAC, OGG, OPUS, WMA, and MP4 input
- Uses Demucs `htdemucs_6s`, which includes a dedicated `guitar` stem
- Keeps generated files, FFmpeg, and model cache out of git
- Uses local FFmpeg portable build when FFmpeg is not available in PATH

## Requirements

- Windows PowerShell
- Python 3.10+
- Internet access for the first setup and first model download

## Quick Start

```powershell
cd D:\Guitar_Spliter
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Open the app:

```text
http://127.0.0.1:7860
```

Upload an audio file, then click **Separate guitar**.

## How It Works

1. The browser uploads audio to the local Python server.
2. The server stores the file under `data/jobs/<job-id>/uploads`.
3. Demucs runs with `--two-stems guitar`.
4. The server exposes download/preview endpoints for:
   - original input
   - guitar-only output
   - no-guitar output

## Project Structure

```text
.
├── app.py                 # Local HTTP server and job API
├── run_demucs.py          # Windows-safe Demucs wrapper
├── sitecustomize.py       # Helps native DLL lookup for local FFmpeg
├── requirements.txt       # Python dependencies
├── scripts/
│   ├── setup.ps1          # Creates .venv, installs deps, downloads FFmpeg
│   └── start.ps1          # Starts the local app
└── static/
    ├── index.html         # Web UI
    ├── styles.css
    └── app.js
```

Generated local folders are ignored by git:

- `.venv/`
- `data/`
- `tools/`

## Configuration

Optional environment variables:

```powershell
$env:GUITAR_SPLITTER_PORT="7860"
$env:DEMUCS_MODEL="htdemucs_6s"
$env:DEMUCS_DEVICE="cpu"
$env:MAX_UPLOAD_MB="250"
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

If you have CUDA configured for PyTorch, you can try:

```powershell
$env:DEMUCS_DEVICE="cuda"
```

## Troubleshooting

If PowerShell blocks scripts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

If the app opens but says setup is missing, rerun:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

If processing is slow, test with a 20-60 second clip first. CPU separation on
full songs can take several minutes.

## Limitations

Guitar separation quality depends heavily on the mix. Clean acoustic or isolated
electric parts work better than dense rock/metal mixes with multiple layered
guitars, synths, or piano in the same frequency range.

## License

MIT. See [LICENSE](LICENSE).


cd D:\Guitar_Spliter
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1