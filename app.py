from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
LOCAL_FFMPEG_BIN = ROOT / "tools" / "ffmpeg" / "bin"
LOCAL_TORCH_HOME = ROOT / "tools" / "model-cache" / "torch"

if LOCAL_FFMPEG_BIN.is_dir():
    os.environ["PATH"] = str(LOCAL_FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", "")
os.environ.setdefault("TORCH_HOME", str(LOCAL_TORCH_HOME))

HOST = os.getenv("GUITAR_SPLITTER_HOST", "127.0.0.1")
PORT = int(os.getenv("GUITAR_SPLITTER_PORT", "7860"))
DEMUCS_MODEL = os.getenv("DEMUCS_MODEL", "htdemucs_6s")
DEMUCS_DEVICE = os.getenv("DEMUCS_DEVICE", "").strip()
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "250"))

ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".mp4",
}

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_TORCH_HOME.mkdir(parents=True, exist_ok=True)


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, message: str, status: int = 200) -> None:
    body = message.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "audio"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("._") or "audio"
    suffix = Path(name).suffix.lower()
    return f"{stem}{suffix}"


def parse_audio_upload(body: bytes, content_type: str) -> tuple[str, bytes] | tuple[None, None]:
    boundary_match = re.search(r'boundary="?([^";]+)"?', content_type)
    if not boundary_match:
        return None, None

    boundary = boundary_match.group(1).encode("utf-8")
    delimiter = b"--" + boundary
    for raw_part in body.split(delimiter):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue

        raw_headers, data = part.split(b"\r\n\r\n", 1)
        headers = raw_headers.decode("iso-8859-1", errors="replace")
        disposition_line = next(
            (line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")),
            "",
        )
        if 'name="audio"' not in disposition_line:
            continue

        filename_match = re.search(r'filename="([^"]*)"', disposition_line)
        if not filename_match or not filename_match.group(1):
            return None, None

        if data.endswith(b"\r\n--"):
            data = data[:-4]
        elif data.endswith(b"\r\n"):
            data = data[:-2]
        return filename_match.group(1), data

    return None, None


def update_job(job_id: str, **updates) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job.update(updates)
        job["updated_at"] = time.time()


def append_log(job_id: str, line: str) -> None:
    line = line.strip()
    if not line:
        return
    with JOBS_LOCK:
        job = JOBS[job_id]
        logs = job.setdefault("logs", [])
        logs.append(line)
        del logs[:-80]
        job["updated_at"] = time.time()


def public_job(job: dict) -> dict:
    result = {
        "id": job["id"],
        "status": job["status"],
        "filename": job["filename"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "model": job["model"],
        "logs": job.get("logs", []),
        "error": job.get("error"),
        "files": {},
    }
    if job.get("original_path"):
        result["files"]["original"] = f"/api/jobs/{job['id']}/files/original"
    if job.get("guitar_path"):
        result["files"]["guitar"] = f"/api/jobs/{job['id']}/files/guitar"
    if job.get("no_guitar_path"):
        result["files"]["no_guitar"] = f"/api/jobs/{job['id']}/files/no_guitar"
    return result


def candidate_pythons() -> list[str]:
    env_python = os.getenv("DEMUCS_PYTHON", "").strip()
    candidates = []
    if env_python:
        candidates.append(env_python)
    candidates.extend(
        [
            str(ROOT / ".venv" / "Scripts" / "python.exe"),
            sys.executable,
            "python",
            "py",
        ]
    )
    seen = set()
    unique = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def check_python_has_demucs(python_exe: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [python_exe, "-c", "import demucs; print('ok')"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        return False, str(exc)
    if completed.returncode == 0:
        return True, python_exe
    detail = (completed.stderr or completed.stdout or "").strip()
    return False, detail


def resolve_demucs_python() -> tuple[str | None, list[str]]:
    errors = []
    for python_exe in candidate_pythons():
        ok, detail = check_python_has_demucs(python_exe)
        if ok:
            return python_exe, errors
        errors.append(f"{python_exe}: {detail}")
    return None, errors


def health_payload() -> dict:
    demucs_python, errors = resolve_demucs_python()
    ffmpeg_ok = command_exists("ffmpeg")
    return {
        "ok": bool(demucs_python and ffmpeg_ok),
        "server_python": sys.executable,
        "demucs_python": demucs_python,
        "demucs_model": DEMUCS_MODEL,
        "ffmpeg": ffmpeg_ok,
        "max_upload_mb": MAX_UPLOAD_MB,
        "setup_hint": "Run scripts/setup.ps1, install FFmpeg, then start the app with scripts/start.ps1.",
        "demucs_errors": errors[-3:],
    }


def locate_output_file(search_root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        matches = sorted(search_root.rglob(name))
        if matches:
            return matches[0]
    lowered = {name.lower() for name in names}
    for file_path in search_root.rglob("*"):
        if file_path.is_file() and file_path.name.lower() in lowered:
            return file_path
    return None


def run_demucs_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        input_path = Path(job["original_path"])
        job_dir = Path(job["job_dir"])

    update_job(job_id, status="running")
    append_log(job_id, f"Using model {DEMUCS_MODEL}.")

    demucs_python, errors = resolve_demucs_python()
    if not demucs_python:
        update_job(
            job_id,
            status="error",
            error="Demucs is not installed in the app environment. Run scripts/setup.ps1 first.",
        )
        for error in errors[-5:]:
            append_log(job_id, error)
        return

    if not command_exists("ffmpeg"):
        update_job(
            job_id,
            status="error",
            error="FFmpeg was not found in PATH. Install FFmpeg and restart this terminal.",
        )
        return

    separated_dir = job_dir / "separated"
    separated_dir.mkdir(parents=True, exist_ok=True)

    command = [
        demucs_python,
        str(ROOT / "run_demucs.py"),
        "--two-stems",
        "guitar",
        "-n",
        DEMUCS_MODEL,
        "--out",
        str(separated_dir),
    ]
    if DEMUCS_DEVICE:
        command.extend(["--device", DEMUCS_DEVICE])
    command.append(str(input_path))

    append_log(job_id, "Starting separation. This can take several minutes on CPU.")
    append_log(job_id, " ".join(command))

    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        append_log(job_id, line)

    return_code = process.wait()
    if return_code != 0:
        update_job(job_id, status="error", error=f"Demucs failed with exit code {return_code}.")
        return

    guitar_source = locate_output_file(separated_dir, ("guitar.wav", "guitar.mp3", "guitar.flac"))
    no_guitar_source = locate_output_file(
        separated_dir,
        ("no_guitar.wav", "no_guitar.mp3", "no_guitar.flac", "noguitar.wav"),
    )

    if not guitar_source or not no_guitar_source:
        update_job(
            job_id,
            status="error",
            error="Demucs finished, but expected guitar/no_guitar files were not found.",
        )
        return

    exports_dir = job_dir / "exports"
    exports_dir.mkdir(exist_ok=True)
    guitar_path = exports_dir / f"guitar{guitar_source.suffix.lower()}"
    no_guitar_path = exports_dir / f"no_guitar{no_guitar_source.suffix.lower()}"
    shutil.copyfile(guitar_source, guitar_path)
    shutil.copyfile(no_guitar_source, no_guitar_path)

    update_job(
        job_id,
        status="done",
        guitar_path=str(guitar_path),
        no_guitar_path=str(no_guitar_path),
    )
    append_log(job_id, "Done.")


class GuitarSplitterHandler(BaseHTTPRequestHandler):
    server_version = "GuitarSplitter/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/":
            self.serve_static(STATIC_DIR / "index.html")
            return
        if path.startswith("/assets/"):
            self.serve_static(STATIC_DIR / path.removeprefix("/assets/"))
            return
        if path == "/api/health":
            json_response(self, health_payload())
            return
        if path.startswith("/api/jobs/"):
            self.handle_job_get(path)
            return
        text_response(self, "Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/jobs":
            self.handle_job_create()
            return
        text_response(self, "Not found", HTTPStatus.NOT_FOUND)

    def serve_static(self, file_path: Path) -> None:
        try:
            resolved = file_path.resolve()
            if STATIC_DIR.resolve() not in resolved.parents and resolved != STATIC_DIR / "index.html":
                text_response(self, "Forbidden", HTTPStatus.FORBIDDEN)
                return
            if not resolved.is_file():
                text_response(self, "Not found", HTTPStatus.NOT_FOUND)
                return
            content = resolved.read_bytes()
        except OSError:
            text_response(self, "Not found", HTTPStatus.NOT_FOUND)
            return

        mime = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def handle_job_get(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            text_response(self, "Not found", HTTPStatus.NOT_FOUND)
            return
        job_id = parts[2]
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if not job:
            text_response(self, "Job not found", HTTPStatus.NOT_FOUND)
            return

        if len(parts) == 3:
            json_response(self, public_job(job))
            return
        if len(parts) == 5 and parts[3] == "files":
            self.serve_job_file(job, parts[4])
            return
        text_response(self, "Not found", HTTPStatus.NOT_FOUND)

    def serve_job_file(self, job: dict, kind: str) -> None:
        field_map = {
            "original": "original_path",
            "guitar": "guitar_path",
            "no_guitar": "no_guitar_path",
        }
        field = field_map.get(kind)
        if not field or not job.get(field):
            text_response(self, "File not found", HTTPStatus.NOT_FOUND)
            return
        file_path = Path(job[field])
        if not file_path.is_file():
            text_response(self, "File not found", HTTPStatus.NOT_FOUND)
            return

        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.end_headers()
        with file_path.open("rb") as file_handle:
            shutil.copyfileobj(file_handle, self.wfile)

    def handle_job_create(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            json_response(self, {"error": "No upload body received."}, HTTPStatus.BAD_REQUEST)
            return
        if content_length > MAX_UPLOAD_MB * 1024 * 1024:
            json_response(
                self,
                {"error": f"File is larger than the {MAX_UPLOAD_MB} MB upload limit."},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return

        body = self.rfile.read(content_length)
        upload_filename, upload_data = parse_audio_upload(body, self.headers.get("Content-Type", ""))
        if not upload_filename or upload_data is None:
            json_response(self, {"error": "Upload field 'audio' is required."}, HTTPStatus.BAD_REQUEST)
            return

        filename = safe_filename(upload_filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            json_response(self, {"error": f"Unsupported audio format: {suffix or 'unknown'}."}, HTTPStatus.BAD_REQUEST)
            return

        job_id = uuid.uuid4().hex
        job_dir = JOBS_DIR / job_id
        uploads_dir = job_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        original_path = uploads_dir / filename

        original_path.write_bytes(upload_data)

        now = time.time()
        job = {
            "id": job_id,
            "status": "queued",
            "filename": filename,
            "created_at": now,
            "updated_at": now,
            "model": DEMUCS_MODEL,
            "job_dir": str(job_dir),
            "original_path": str(original_path),
            "guitar_path": None,
            "no_guitar_path": None,
            "error": None,
            "logs": ["Upload received."],
        }
        with JOBS_LOCK:
            JOBS[job_id] = job

        thread = threading.Thread(target=run_demucs_job, args=(job_id,), daemon=True)
        thread.start()
        json_response(self, public_job(job), HTTPStatus.CREATED)

    def log_message(self, format: str, *args) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), format % args))


def main() -> None:
    ensure_dirs()
    server = ThreadingHTTPServer((HOST, PORT), GuitarSplitterHandler)
    print(f"Guitar Splitter is running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
