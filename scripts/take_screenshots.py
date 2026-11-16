"""Take the README screenshots of the web interface with a real browser.

    python scripts/take_screenshots.py

Starts the app on a temporary data folder filled with the example analyses,
uploads a generated video to show a running analysis, then captures each page.
Needs: pip install -e ".[dev]" && playwright install chromium
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from conftest import free_port  # noqa: E402

from shapeofmovie.models import MovieShape  # noqa: E402
from shapeofmovie.web.store import slugify  # noqa: E402

OUT = ROOT / "docs" / "screenshots"
VIEWPORT = {"width": 1280, "height": 860}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    shapes = tmp / "data" / "shapes"
    shapes.mkdir(parents=True)
    for i, src in enumerate(sorted((ROOT / "examples" / "mean").glob("*.json"))):
        shape = MovieShape.load(src)
        shape.method = "linear" if i % 2 else "mean"
        shape.save(shapes / f"{slugify(shape.title)}-{i:06x}.json")

    # a long-ish 1080p video, so the analysis is still running for the screenshot
    video = tmp / "Big Buck Test.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=1920x1080:r=24:d=240",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            str(video),
        ],
        check=True,
    )

    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "shapeofmovie.cli", "serve", "--port", str(port), "--data", str(tmp / "data")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT)
            for _ in range(50):
                try:
                    page.goto(base)
                    break
                except Exception:
                    page.wait_for_timeout(200)

            # home: gallery
            page.wait_for_load_state("networkidle")
            page.locator("#gallery").screenshot(path=OUT / "gallery.png")

            # home: upload with an analysis in progress
            page.get_by_test_id("file-input").set_input_files(video)
            page.get_by_label("Titre").fill("Big Buck Test")
            page.get_by_role("button", name="Lancer l'analyse").click()
            expect(page.get_by_test_id("job").first).to_contain_text("échantillons", timeout=30_000)
            progress = "document.querySelector('[data-testid=job] progress')?.value || 0"
            page.wait_for_function(f"() => ({progress}) >= 25", timeout=60_000)
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=OUT / "home.png")

            # error cases: refused file type and corrupted video
            all_finished = (
                "[...document.querySelectorAll('[data-testid=job]')].every(j => !j.hasAttribute('hx-get'))"
            )
            page.wait_for_function(f"() => {all_finished}", timeout=120_000)
            bad_txt, bad_mp4 = tmp / "notes.txt", tmp / "Fichier abimé.mp4"
            bad_txt.write_text("not a video")
            bad_mp4.write_bytes(b"\x00" * 4096)
            for bad in (bad_mp4, bad_txt):
                page.get_by_test_id("file-input").set_input_files(bad)
                page.get_by_role("button", name="Lancer l'analyse").click()
                page.wait_for_timeout(300)
            expect(page.get_by_test_id("upload-error")).to_be_visible()
            expect(page.locator(".job-error").filter(has_text="Fichier abimé")).to_contain_text(
                "Échec", timeout=30_000
            )
            page.locator("#upload").screenshot(path=OUT / "errors.png")

            # movie page with the timeline tooltip
            page.goto(f"{base}/movies/{next(shapes.glob('spider-man*')).stem}")
            page.wait_for_load_state("networkidle")
            timeline = page.get_by_test_id("timeline")
            expect(timeline).to_have_attribute("data-ready", "1")
            box = timeline.bounding_box()
            page.mouse.move(box["x"] + box["width"] * 0.62, box["y"] + box["height"] / 2)
            page.screenshot(path=OUT / "movie.png", full_page=False)

            # render controls: ring style
            page.get_by_test_id("style-select").select_option("ring")
            page.locator("input[name=smooth]").fill("15")
            page.locator("input[name=smooth]").dispatch_event("input")
            page.wait_for_function(
                "() => { const i = document.querySelector('[data-testid=preview-image]');"
                " return i.src.includes('smooth=15') && i.complete && i.naturalWidth > 0 }"
            )
            page.mouse.move(0, 0)
            page.locator("section.panel").nth(2).screenshot(path=OUT / "render.png")
            browser.close()
    finally:
        server.terminate()
        server.wait()
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"screenshots written to {OUT}")


if __name__ == "__main__":
    main()
