import logging
import time

import pytest
from fastapi.testclient import TestClient

from shapeofmovie import analyze
from shapeofmovie.cli import main
from shapeofmovie.logs import setup_logging
from shapeofmovie.web import Settings, create_app


@pytest.fixture(autouse=True)
def restore_logging():
    yield
    setup_logging("WARNING")


def test_setup_logging_writes_file(tmp_path, monkeypatch):
    log_file = tmp_path / "logs" / "som.log"
    monkeypatch.setenv("SOM_LOG_LEVEL", "debug")
    setup_logging(file=log_file)
    logging.getLogger("shapeofmovie.test").debug("hello %s", "file")
    for h in logging.getLogger().handlers:
        h.flush()
    line = log_file.read_text().strip()
    assert line.endswith("DEBUG   shapeofmovie.test: hello file")


def test_invalid_level_is_rejected():
    with pytest.raises(ValueError):
        setup_logging("LOUD")


def test_analysis_is_logged(rgb_video, caplog):
    caplog.set_level(logging.INFO, logger="shapeofmovie")
    analyze(rgb_video)
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("analysing ") and "320x180" in m for m in messages)
    assert any(m.startswith("analysed ") and "6 samples" in m for m in messages)


def test_cli_log_options(rgb_video, tmp_path):
    log_file = tmp_path / "cli.log"
    assert (
        main(
            [
                "--log-level",
                "INFO",
                "--log-file",
                str(log_file),
                "analyze",
                str(rgb_video),
                "-o",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert "analysed" in log_file.read_text()


def test_web_job_lifecycle_is_logged(rgb_video, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="shapeofmovie")
    with TestClient(create_app(Settings(data_dir=tmp_path / "data"))) as client:
        with open(rgb_video, "rb") as f:
            job_id = client.post("/api/analyses", files={"file": (rgb_video.name, f)}).json()["id"]
        for _ in range(100):
            if client.get(f"/api/jobs/{job_id}").json()["status"] == "done":
                break
            time.sleep(0.1)
    text = "\n".join(r.getMessage() for r in caplog.records)
    for expected in ("starting", "upload received", f"job {job_id} queued", f"job {job_id} started",
                     f"job {job_id} done", "saved movie"):  # fmt: skip
        assert expected in text, expected
