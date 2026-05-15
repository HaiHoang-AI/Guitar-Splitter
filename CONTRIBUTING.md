# Contributing

Thanks for improving Guitar Splitter.

## Local Development

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Open `http://127.0.0.1:7860`.

## Before Opening a Pull Request

- Keep generated audio, models, FFmpeg builds, and virtual environments out of git.
- Run a smoke test with a short audio clip.
- Keep UI changes responsive on narrow and desktop widths.
- Update `README.md` when setup, behavior, or configuration changes.

## Code Style

- Prefer standard-library code unless a dependency clearly pays for itself.
- Keep backend behavior explicit and easy to debug.
- Avoid unrelated refactors in feature or bug-fix PRs.
