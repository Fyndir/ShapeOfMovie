import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest


def make_video(path: Path, colors=("red", "green", "blue"), seconds=2, size="320x180") -> Path:
    """Build a real H.264 video made of solid-colour segments."""
    inputs = []
    for color in colors:
        inputs += ["-f", "lavfi", "-i", f"color=c={color}:s={size}:r=24:d={seconds}"]
    concat = "".join(f"[{i}]" for i in range(len(colors))) + f"concat=n={len(colors)}:v=1"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            *inputs,
            "-filter_complex",
            concat,
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture(scope="session")
def rgb_video(tmp_path_factory) -> Path:
    """6 s test video: 2 s red, 2 s green, 2 s blue."""
    return make_video(tmp_path_factory.mktemp("video") / "Red Green Blue.mp4")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server(tmp_path):
    """Run the real web app with uvicorn on a free port, with an empty data folder."""
    import uvicorn

    from shapeofmovie.web import Settings, create_app

    port = free_port()
    app = create_app(Settings(data_dir=tmp_path / "data"))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
