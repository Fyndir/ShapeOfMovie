"""Background analyses.

Jobs live in memory: on restart, unfinished ones are lost and their uploads are
cleaned up (see `JobManager.cleanup_uploads`). Good enough for a personal server.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from shapeofmovie.analyze import analyze
from shapeofmovie.extract import FFmpegError
from shapeofmovie.web.store import ShapeStore

log = logging.getLogger(__name__)


class Status(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class Job:
    id: str
    title: str
    filename: str
    method: str
    step: float
    status: Status = Status.QUEUED
    done: int = 0
    total: int | None = None
    movie_id: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def percent(self) -> int:
        if self.status == Status.DONE:
            return 100
        if not self.total:
            return 0
        return min(99, self.done * 100 // self.total)

    @property
    def eta_seconds(self) -> int | None:
        if self.status != Status.RUNNING or not self.total or not self.done or not self.started_at:
            return None
        elapsed = time.time() - self.started_at
        return int(elapsed / self.done * (self.total - self.done))

    @property
    def finished(self) -> bool:
        return self.status in (Status.DONE, Status.ERROR)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "percent": self.percent,
            "done": self.done,
            "total": self.total,
            "eta_seconds": self.eta_seconds,
            "movie_id": self.movie_id,
            "error": self.error,
        }


class JobManager:
    def __init__(self, store: ShapeStore, uploads_dir: Path, workers: int = 1) -> None:
        self.store = store
        self.uploads_dir = uploads_dir
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="analysis")

    def cleanup_uploads(self) -> None:
        for leftover in self.uploads_dir.iterdir():
            log.warning("removing upload left over by a previous run: %s", leftover.name)
            leftover.unlink(missing_ok=True)

    def new_upload_path(self, suffix: str) -> Path:
        return self.uploads_dir / f"{uuid.uuid4().hex}{suffix}"

    def submit(self, video: Path, *, title: str, filename: str, method: str, step: float) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], title=title, filename=filename, method=method, step=step)
        with self._lock:
            self._jobs[job.id] = job
        log.info("job %s queued: %r (%s, method=%s, step=%s)", job.id, title, filename, method, step)
        self._pool.submit(self._run, job, video)
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            return self._jobs[job_id]

    def active(self) -> list[Job]:
        with self._lock:
            jobs = [j for j in self._jobs.values() if not j.finished]
        return sorted(jobs, key=lambda j: j.created_at)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _run(self, job: Job, video: Path) -> None:
        job.status = Status.RUNNING
        log.info("job %s started", job.id)
        job.started_at = time.time()

        def progress(done: int, total: int | None) -> None:
            job.done, job.total = done, total

        try:
            shape = analyze(video, method=job.method, step=job.step, title=job.title, progress=progress)
            if len(shape) == 0:
                raise FFmpegError("no frame could be read")
            shape.source = job.filename  # don't leak the server-side temp path
            shape.meta["origin"] = "upload"
            movie_id = self.store.new_id(job.title)
            self.store.save(movie_id, shape)
            job.movie_id = movie_id
            job.status = Status.DONE
            log.info("job %s done -> movie %s (%.1f s)", job.id, movie_id, time.time() - job.started_at)
        except FFmpegError as exc:
            # details (with server paths) go to the logs only, the user gets a clear message
            log.warning("job %s: unreadable video %s: %s", job.id, job.filename, exc)
            job.error = "Vidéo illisible : le fichier est endommagé ou n'est pas une vidéo."
            job.status = Status.ERROR
        except Exception:  # never crashes the worker
            log.exception("job %s: analysis of %s failed", job.id, job.filename)
            job.error = "Erreur inattendue pendant l'analyse (détails dans les logs du serveur)."
            job.status = Status.ERROR
        finally:
            job.finished_at = time.time()
            video.unlink(missing_ok=True)  # the video is never kept, only its shape
