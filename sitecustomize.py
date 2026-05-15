from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOCAL_FFMPEG_BIN = Path(os.getenv("GUITAR_SPLITTER_FFMPEG_BIN", ROOT / "tools" / "ffmpeg" / "bin"))

_DLL_DIRECTORY_HANDLE = None

if LOCAL_FFMPEG_BIN.is_dir() and hasattr(os, "add_dll_directory"):
    _DLL_DIRECTORY_HANDLE = os.add_dll_directory(str(LOCAL_FFMPEG_BIN))
