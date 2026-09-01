"""FFmpeg/ffprobe discovery and subprocess helpers."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

COMMON_FFMPEG_LOCATIONS = (
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\Tools\ffmpeg\bin\ffmpeg.exe",
)


class FFmpegError(Exception):
    """Raised when an ffmpeg invocation fails."""


def find_ffmpeg() -> str | None:
    """Locate the ffmpeg binary (env override -> PATH -> common locations)."""
    override = os.environ.get("FFMPEG_BIN")
    if override:
        candidate = Path(os.path.expandvars(override).strip().strip('"'))
        if candidate.exists():
            return str(candidate)
        logger.warning("FFMPEG_BIN set to %r but file does not exist", override)

    found = shutil.which("ffmpeg")
    if found:
        return found

    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        winget_pkgs = Path(localappdata) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for pkg_dir in winget_pkgs.glob("*FFmpeg*"):
                globbed = sorted(pkg_dir.rglob("ffmpeg.exe"))
                if globbed:
                    return str(globbed[0])
            for pkg_dir in winget_pkgs.glob("*ffmpeg*"):
                globbed = sorted(pkg_dir.rglob("ffmpeg.exe"))
                if globbed:
                    return str(globbed[0])

    for pattern in COMMON_FFMPEG_LOCATIONS:
        candidate = Path(pattern)
        if candidate.exists():
            return str(candidate)
    return None


def has_ffmpeg() -> bool:
    return find_ffmpeg() is not None


def run_ffmpeg(
    args: list[str],
    *,
    cwd: str | Path | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    """Run an ffmpeg/ffprobe command and raise :class:`FFmpegError` on failure."""
    binary = find_ffmpeg()
    if binary is None:
        raise FFmpegError("ffmpeg was not found; see the project README to install it")
    cmd = [binary, *args]
    logger.debug("Running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError("ffmpeg timed out") from exc

    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-15:])
        raise FFmpegError(f"ffmpeg exited with code {proc.returncode}:\n{tail}")
    return proc


def probe_duration(media_path: str | Path) -> float:
    """Return the duration (seconds) of a media file via ffprobe."""
    binary = find_ffmpeg()
    if binary is None:
        raise FFmpegError("ffmpeg was not found; cannot probe media")
    ffprobe = str(Path(binary).with_name("ffprobe.exe"))
    if not Path(ffprobe).exists():
        # macOS/Linux naming
        ffprobe = str(Path(binary).with_name("ffprobe"))
    if not Path(ffprobe).exists():
        raise FFmpegError("ffprobe was not found next to ffmpeg")

    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError("ffprobe timed out") from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise FFmpegError(f"ffprobe could not read duration of {media_path}")
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise FFmpegError(f"unexpected duration output for {media_path}") from exc