"""HTTP-level tests of the web app (no browser)."""

import time

import pytest
from fastapi.testclient import TestClient

from shapeofmovie.web import Settings, create_app
from shapeofmovie.web.store import slugify


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path / "data"))) as c:
        yield c


def wait_job(client, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.2)
    raise AssertionError("analysis did not finish")


def upload(client, path, **data):
    with open(path, "rb") as f:
        return client.post("/api/analyses", files={"file": (path.name, f, "video/mp4")}, data=data)


def test_full_api_flow(client, rgb_video, tmp_path):
    assert client.get("/api/movies").json() == []

    r = upload(client, rgb_video, title="Mon film", method="mean", step="1")
    assert r.status_code == 202
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "done", job
    movie_id = job["movie_id"]
    assert movie_id.startswith("mon-film-")

    movies = client.get("/api/movies").json()
    assert [m["id"] for m in movies] == [movie_id]
    assert movies[0]["samples"] == 6

    movie = client.get(f"/api/movies/{movie_id}").json()
    r0, g0, b0 = bytes.fromhex(movie["colors"][0])
    assert r0 > 240 and g0 < 15 and b0 < 15  # first second is red (yuv420p is slightly lossy)
    assert len(movie["palette"]) >= 3

    for style in ("barcode", "vertical", "ring"):
        img = client.get(f"/movies/{movie_id}/image.png", params={"style": style, "width": 200, "height": 50})
        assert img.status_code == 200 and img.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert (
        "attachment" in client.get(f"/movies/{movie_id}/shape.json?download=1").headers["content-disposition"]
    )
    assert client.get(f"/movies/{movie_id}").status_code == 200

    # the uploaded video is deleted once analysed
    assert list((tmp_path / "data" / "uploads").iterdir()) == []

    assert client.delete(f"/movies/{movie_id}").status_code == 204
    assert client.get(f"/movies/{movie_id}").status_code == 404


def test_rejects_non_video_extension(client, tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    assert upload(client, bad).status_code == 415


def test_corrupted_video_reports_error(client, tmp_path):
    fake = tmp_path / "broken.mp4"
    fake.write_bytes(b"\x00" * 4096)
    job = wait_job(client, upload(client, fake).json()["id"])
    assert job["status"] == "error" and job["error"]
    assert client.get("/api/movies").json() == []


def test_rejects_bad_parameters(client, rgb_video):
    assert upload(client, rgb_video, method="nope").status_code == 422
    assert upload(client, rgb_video, step="0").status_code == 422


def test_upload_size_limit(tmp_path, rgb_video):
    with TestClient(create_app(Settings(data_dir=tmp_path / "d", max_upload_mb=0))) as c:
        assert upload(c, rgb_video).status_code == 413
        assert list((tmp_path / "d" / "uploads").iterdir()) == []


@pytest.mark.parametrize("movie_id", ["../../etc/passwd", "UPPER", "a" * 200])
def test_invalid_ids_are_404(client, movie_id):
    assert client.get(f"/api/movies/{movie_id}").status_code == 404


def test_slugify():
    assert slugify("Le Fabuleux Destin d'Amélie Poulain") == "le-fabuleux-destin-d-amelie-poulain"
    assert slugify("???") == "movie"
