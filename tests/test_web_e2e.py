"""Browser end-to-end tests: a real Chromium drives the real server.

Run with: pytest -m e2e   (needs `playwright install chromium` once)
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_upload_analyse_explore_delete(live_server, page: Page, rgb_video, tmp_path):
    # 1. empty home page
    page.goto(live_server)
    expect(page.get_by_role("heading", name="Un film entier, en une seule image.")).to_be_visible()
    expect(page.get_by_text("Aucun film pour l'instant")).to_be_visible()

    # 2. upload a video through the form
    page.get_by_test_id("file-input").set_input_files(rgb_video)
    expect(page.locator(".dropzone-text")).to_contain_text("Red Green Blue.mp4")
    page.get_by_label("Titre").fill("Rouge Vert Bleu")
    page.get_by_role("button", name="Lancer l'analyse").click()

    # 3. the job appears, progresses, finishes, and the gallery refreshes by itself
    job = page.get_by_test_id("job").first
    expect(job).to_contain_text("Rouge Vert Bleu")
    expect(job).to_contain_text("Terminé", timeout=30_000)
    card = page.get_by_test_id("movie-card")
    expect(card).to_have_count(1)
    expect(card).to_contain_text("Rouge Vert Bleu")
    expect(card).to_contain_text("0:06")
    expect(page.locator("#upload-form .dropzone-text")).to_contain_text("Glisse une vidéo")  # form was reset

    # 4. movie page
    job.get_by_role("link", name="Voir le résultat").click()
    expect(page).to_have_url(re.compile(r"/movies/rouge-vert-bleu-[0-9a-f]{6}$"))
    expect(page.get_by_role("heading", name="Rouge Vert Bleu")).to_be_visible()
    expect(page.locator(".facts")).to_contain_text("6")

    # 5. hovering the timeline shows time and colour
    timeline = page.get_by_test_id("timeline")
    expect(timeline).to_have_attribute("data-ready", "1")
    box = timeline.bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.1, box["y"] + box["height"] / 2)
    expect(timeline.locator(".tooltip")).to_contain_text(re.compile(r"0:0[01] · #f[0-9a-f]0[0-9a-f]0"))
    page.mouse.move(box["x"] + box["width"] * 0.9, box["y"] + box["height"] / 2)
    expect(timeline.locator(".tooltip")).to_contain_text(re.compile(r"0:05 · #0"))

    # 6. palette and style switch (HTMX swaps the preview)
    assert page.get_by_test_id("palette").locator("li").count() >= 3
    page.get_by_test_id("style-select").select_option("ring")
    preview = page.get_by_test_id("preview-image")
    expect(preview).to_have_attribute("src", re.compile("style=ring"))
    page.wait_for_function("() => document.querySelector('[data-testid=preview-image]').naturalWidth > 0")

    # 7. delete, back to an empty gallery
    page.once("dialog", lambda d: d.accept())
    page.get_by_role("button", name="Supprimer ce film").click()
    expect(page).to_have_url(live_server + "/")
    expect(page.get_by_text("Aucun film pour l'instant")).to_be_visible()


def test_upload_refused_file_shows_error(live_server, page: Page, tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("not a video")
    page.goto(live_server)
    page.get_by_test_id("file-input").set_input_files(bad)
    page.get_by_role("button", name="Lancer l'analyse").click()
    expect(page.get_by_test_id("upload-error")).to_contain_text("format non pris en charge")


def test_unknown_movie_is_404(live_server, page: Page):
    response = page.goto(live_server + "/movies/does-not-exist")
    assert response.status == 404
