"""Frame sampling, delegated to ffmpeg.

ffmpeg decodes, drops the frames we don't need and downscales in a single pass,
then streams raw RGB pixels to us: nothing is written to disk. Because ffmpeg
reads URLs too, the same code works on a local file or a Jellyfin stream.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

VIDEO_EXTENSIONS = {".avi", ".mkv", ".mp4", ".mov", ".m4v", ".webm", ".wmv", ".ts"}


class FFmpegError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration: float | None


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise FFmpegError(f"'{binary}' not found: install ffmpeg and make sure it is on PATH")
    return path


def probe(source: str) -> VideoInfo:
    """Read the dimensions and duration of the first video stream."""
    cmd = [
        _require("ffprobe"),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        source,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {source}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    if not data.get("streams"):
        raise FFmpegError(f"no video stream in {source}")
    stream = data["streams"][0]
    duration = data.get("format", {}).get("duration")
    return VideoInfo(
        width=int(stream["width"]),
        height=int(stream["height"]),
        duration=float(duration) if duration not in (None, "N/A") else None,
    )


def iter_frames(
    source: str,
    step: float = 1.0,
    width: int = 160,
    info: VideoInfo | None = None,
) -> Iterator[np.ndarray]:
    """Yield one small RGB frame (h, w, 3 uint8) every `step` seconds."""
    if step <= 0:
        raise ValueError("step must be > 0")
    info = info or probe(source)
    height = max(2, round(width * info.height / info.width / 2) * 2)
    frame_bytes = width * height * 3
    cmd = [
        _require("ffmpeg"),
        "-nostdin",
        "-loglevel",
        "error",
        "-i",
        source,
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        # area scaling = averaging of source pixels, so colours are preserved
        "-vf",
        f"fps=1/{step},scale={width}:{height}:flags=area",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            yield np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3)
    finally:
        proc.stdout.close()
        if proc.poll() is None:  # consumer stopped early
            proc.kill()
        proc.wait()
        stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        if proc.stderr:
            proc.stderr.close()
    if proc.returncode not in (0, -9):
        raise FFmpegError(f"ffmpeg failed on {source}: {stderr.strip()}")
