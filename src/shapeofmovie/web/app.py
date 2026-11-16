"""FastAPI application: HTML pages (Jinja + HTMX) and a small JSON API."""

from __future__ import annotations

import io
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from shapeofmovie import __version__
from shapeofmovie.analyze import title_from_source
from shapeofmovie.colors import METHODS
from shapeofmovie.extract import VIDEO_EXTENSIONS
from shapeofmovie.models import MovieShape
from shapeofmovie.render import STYLES, render
from shapeofmovie.web.config import Settings
from shapeofmovie.web.jobs import JobManager
from shapeofmovie.web.store import ShapeStore

log = logging.getLogger(__name__)
HERE = Path(__file__).parent
CHUNK = 1024 * 1024
METHOD_LABELS = {
    "linear": "Moyenne perceptuelle",
    "mean": "Moyenne RGB",
    "median": "Médiane",
    "dominant": "Couleur dominante (k-means, lent)",
}
STYLE_LABELS = {"barcode": "Code-barres", "vertical": "Vertical", "ring": "Anneau"}


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def palette(shape: MovieShape, n: int = 6) -> list[str]:
    """The n colours that best summarise the whole movie, most frequent first."""
    if len(shape) == 0:
        return []
    img = Image.fromarray(shape.colors[np.newaxis, :, :], "RGB").quantize(
        colors=n, method=Image.Quantize.MEDIANCUT
    )
    pal = img.getpalette()[: 3 * n]
    counts = sorted(img.getcolors(), reverse=True)
    return ["#" + bytes(pal[3 * i : 3 * i + 3]).hex() for _, i in counts]


def movie_summary(movie_id: str, shape: MovieShape) -> dict:
    duration = shape.duration or (len(shape) * shape.step if shape.step else None)
    return {
        "id": movie_id,
        "title": shape.title,
        "method": shape.method,
        "step": shape.step,
        "duration": duration,
        "samples": len(shape),
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = ShapeStore(settings.shapes_dir)
    jobs = JobManager(store, settings.uploads_dir, workers=settings.workers)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        log.info("Shape Of Movie %s starting, data in %s", __version__, settings.data_dir.resolve())
        jobs.cleanup_uploads()
        yield
        log.info("shutting down")
        jobs.shutdown()

    app = FastAPI(title="Shape Of Movie", version=__version__, lifespan=lifespan)
    app.state.settings, app.state.store, app.state.jobs = settings, store, jobs

    @app.middleware("http")
    async def log_errors(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error on %s %s", request.method, request.url.path)
            raise
        if response.status_code >= 500:
            log.error("%s %s -> %d", request.method, request.url.path, response.status_code)
        elif time.perf_counter() - started > 2:
            log.warning(
                "slow request %s %s (%.1f s)", request.method, request.url.path, time.perf_counter() - started
            )
        return response

    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters["duration"] = fmt_duration
    templates.env.globals.update(
        version=__version__,
        methods=METHOD_LABELS,
        styles=STYLE_LABELS,
        settings=settings,
        accept=",".join(sorted(VIDEO_EXTENSIONS)),
    )

    def page(request: Request, name: str, **ctx) -> HTMLResponse:
        return templates.TemplateResponse(request, name, ctx)

    def get_shape(movie_id: str) -> MovieShape:
        try:
            return store.get(movie_id)
        except KeyError:
            raise HTTPException(404, "film introuvable") from None

    async def receive_upload(request: Request, file: UploadFile, title: str, method: str, step: float):
        if method not in METHODS:
            raise HTTPException(422, f"méthode inconnue : {method}")
        if not 0.1 <= step <= 60:
            raise HTTPException(422, "l'intervalle doit être compris entre 0,1 et 60 secondes")
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            log.warning("upload refused, unsupported extension: %s", file.filename)
            raise HTTPException(415, f"format non pris en charge ({suffix or 'sans extension'})")
        limit = settings.max_upload_mb * CHUNK
        if int(request.headers.get("content-length", 0)) > limit + CHUNK:
            raise HTTPException(413, f"fichier trop volumineux (max {settings.max_upload_mb} Mo)")

        target = jobs.new_upload_path(suffix)
        written = 0
        try:
            with target.open("wb") as out:
                while chunk := await file.read(CHUNK):
                    written += len(chunk)
                    if written > limit:
                        raise HTTPException(413, f"fichier trop volumineux (max {settings.max_upload_mb} Mo)")
                    out.write(chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        log.info("upload received: %s (%.1f MB)", file.filename, written / 1e6)
        if written == 0:
            target.unlink(missing_ok=True)
            raise HTTPException(422, "fichier vide")
        clean_title = title.strip() or title_from_source(file.filename or "film")
        return jobs.submit(target, title=clean_title, filename=file.filename or "", method=method, step=step)

    # --- HTML pages --------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        movies = [movie_summary(i, s) for i, s in store.list()]
        return page(request, "index.html", movies=movies, active_jobs=jobs.active())

    @app.get("/fragments/gallery", response_class=HTMLResponse)
    def gallery_fragment(request: Request):
        movies = [movie_summary(i, s) for i, s in store.list()]
        return page(request, "_gallery.html", movies=movies)

    @app.post("/upload", response_class=HTMLResponse)
    async def upload(
        request: Request,
        file: Annotated[UploadFile, File()],
        title: Annotated[str, Form()] = "",
        method: Annotated[str, Form()] = "linear",
        step: Annotated[float, Form()] = 1.0,
    ):
        try:
            job = await receive_upload(request, file, title, method, step)
        except HTTPException as exc:
            return page(request, "_upload_error.html", message=exc.detail)
        return page(request, "_job.html", job=job)

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    def job_fragment(request: Request, job_id: str):
        try:
            job = jobs.get(job_id)
        except KeyError:
            raise HTTPException(404, "analyse introuvable") from None
        response = page(request, "_job.html", job=job)
        if job.movie_id:
            response.headers["HX-Trigger"] = "movie-added"  # refreshes the gallery
        return response

    @app.get("/movies/{movie_id}", response_class=HTMLResponse)
    def movie_page(request: Request, movie_id: str):
        shape = get_shape(movie_id)
        return page(
            request,
            "movie.html",
            movie=movie_summary(movie_id, shape),
            palette=palette(shape),
            source=shape.source,
        )

    @app.get("/movies/{movie_id}/preview", response_class=HTMLResponse)
    def preview_fragment(request: Request, movie_id: str, style: str = "barcode", smooth: int = 0):
        get_shape(movie_id)
        if style not in STYLES:
            style = "barcode"
        return page(request, "_preview.html", movie_id=movie_id, style=style, smooth=max(0, min(smooth, 120)))

    @app.delete("/movies/{movie_id}")
    def delete_movie(movie_id: str):
        get_shape(movie_id)
        store.delete(movie_id)
        return Response(status_code=204, headers={"HX-Redirect": "/"})

    # --- images & data -----------------------------------------------------------

    @app.get("/movies/{movie_id}/image.png")
    def movie_image(
        movie_id: str,
        style: Annotated[str, Query(pattern="^(barcode|vertical|ring)$")] = "barcode",
        width: Annotated[int, Query(ge=16, le=4096)] = 1200,
        height: Annotated[int, Query(ge=16, le=4096)] = 300,
        smooth: Annotated[int, Query(ge=0, le=120)] = 0,
        download: bool = False,
    ):
        shape = get_shape(movie_id)
        buf = io.BytesIO()
        render(shape, style=style, width=width, height=height, smooth=smooth).save(buf, "PNG", optimize=True)
        headers = {"Cache-Control": "private, max-age=3600"}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{movie_id}.{style}.png"'
        return Response(buf.getvalue(), media_type="image/png", headers=headers)

    @app.get("/movies/{movie_id}/shape.json")
    def movie_json(movie_id: str, download: bool = False):
        headers = {}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{movie_id}.json"'
        return JSONResponse(get_shape(movie_id).to_dict(), headers=headers)

    # --- JSON API ----------------------------------------------------------------

    @app.get("/api/movies")
    def api_movies():
        return [movie_summary(i, s) for i, s in store.list()]

    @app.get("/api/movies/{movie_id}")
    def api_movie(movie_id: str):
        shape = get_shape(movie_id)
        return {
            **movie_summary(movie_id, shape),
            "palette": palette(shape),
            "colors": shape.to_dict()["colors"],
        }

    @app.post("/api/analyses", status_code=202)
    async def api_analyze(
        request: Request,
        file: Annotated[UploadFile, File()],
        title: Annotated[str, Form()] = "",
        method: Annotated[str, Form()] = "linear",
        step: Annotated[float, Form()] = 1.0,
    ):
        return (await receive_upload(request, file, title, method, step)).to_dict()

    @app.get("/api/jobs/{job_id}")
    def api_job(job_id: str):
        try:
            return jobs.get(job_id).to_dict()
        except KeyError:
            raise HTTPException(404, "analyse introuvable") from None

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": __version__}

    return app
