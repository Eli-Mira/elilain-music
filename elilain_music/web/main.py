"""FastAPI web dashboard — same engine, browser UI.

    python -m elilain_music.web            # http://127.0.0.1:8081
    python -m elilain_music.web --port 9000

Binds to 127.0.0.1 only. This exposes a downloader with filesystem write
access; it must never be reachable from the network.
"""

from __future__ import annotations

import logging
import sys
import threading
import uuid
import webbrowser
from dataclasses import asdict, dataclass, field

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from ..engine import Downloader, DownloadJob, EngineConfig, Quality, Track
from ..gui.settings import Settings
from ..gui.theme import DARK, LIGHT
from ..gui.wired import ART_DIR

log = logging.getLogger("elilain.web")

HOST = "127.0.0.1"
PORT = 8081

STATUS_TEXT = {
    "downloading": "Downloading",
    "extracting": "Converting",
    "processing": "Converting",
    "tagging": "Tagging",
    "merging": "Merging",
    "done": "Done",
}


# ==================================================================== #
@dataclass
class Job:
    id: str
    url: str
    quality: str
    output_dir: str
    state: str = "queued"        # queued | running | done | error | cancelled
    percent: float = 0.0
    speed: float = 0.0
    eta: float = 0.0
    status_text: str = "Queued"
    path: str = ""
    files: list[str] = field(default_factory=list)
    error: str = ""
    elapsed: float = 0.0

    def public(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "label": self.url.rsplit("/", 1)[-1][:80] or self.url[:80],
            "quality": self.quality,
            "state": self.state,
            "percent": round(self.percent, 1),
            "speed": round(self.speed, 1),
            "eta": round(self.eta, 1),
            "status_text": self.status_text,
            "path": self.path,
            "files": self.files,
            "error": self.error,
            "elapsed": round(self.elapsed, 1),
        }


class JobStore:
    """In-memory registry, oldest-evicted past `limit`."""

    def __init__(self, limit: int = 200) -> None:
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()
        self._limit = limit

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > self._limit:
                self._jobs.pop(self._order.pop(0), None)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        with self._lock:
            return [self._jobs[i] for i in reversed(self._order) if i in self._jobs]

    def clear(self) -> int:
        with self._lock:
            n = len(self._order)
            self._jobs.clear()
            self._order.clear()
            return n

    def drop(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._jobs.pop(job_id, None)
            self._order = [i for i in self._order if i != job_id]
            return True


# ==================================================================== #
class DownloadRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    quality: str = "high"
    output_dir: str = ""
    embed_metadata: bool = True
    embed_thumbnail: bool = True


class ThemeRequest(BaseModel):
    mode: str


# ==================================================================== #
def create_app() -> FastAPI:
    app = FastAPI(title="EliLain-Music", version="0.2.0")
    settings = Settings()
    downloader = Downloader(EngineConfig(output_dir=settings.get("output_dir")))
    store = JobStore()
    dl_lock = threading.Lock()

    # NOTE: the request models live at module scope on purpose. This module
    # uses `from __future__ import annotations`, so FastAPI sees the
    # annotation as the *string* "DownloadRequest" and resolves it against
    # module globals. A class defined inside create_app() is not there, and
    # FastAPI silently degrades the body into query parameters (422).

    @app.get("/art/{name}")
    def artwork(name: str) -> FileResponse:
        if name not in {"lain.png", "wired-city.png", "wired-banner.png", "lain.ico"}:
            raise HTTPException(404, "no such artwork")
        path = ART_DIR / name
        if not path.is_file():
            raise HTTPException(404, "artwork unavailable")
        return FileResponse(path)

    # ------------------------------------------------------------------ #
    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "yt_dlp": Downloader.version(),
            "ffmpeg": bool(EngineConfig().ffmpeg_bin),
            "active": downloader.active_count,
            "jobs": len(store.all()),
            "theme": settings.get("theme"),
        }

    @app.get("/api/palettes")
    def palettes() -> dict:
        return {"dark": asdict(DARK), "light": asdict(LIGHT)}

    @app.post("/api/theme")
    def set_theme(req: ThemeRequest) -> dict:
        mode = req.mode if req.mode in ("dark", "light") else "dark"
        settings.set("theme", mode)
        settings.save()
        return {"theme": mode}

    @app.get("/api/jobs")
    def list_jobs() -> dict:
        return {"jobs": [j.public() for j in store.all()]}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "no such job")
        return job.public()

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "no such job")
        with dl_lock:
            downloader.cancel_all()
        job.state = "cancelled"
        job.status_text = "Cancelled"
        return job.public()

    @app.delete("/api/jobs/finished")
    def clear_finished() -> dict:
        """Drop every terminal job; leave queued/running ones alone."""
        removed = 0
        for job in store.all():
            if job.state in ("done", "error", "cancelled") and store.drop(job.id):
                removed += 1
        return {"removed": removed}

    @app.delete("/api/jobs")
    def clear_jobs() -> dict:
        with dl_lock:
            downloader.cancel_all()
        return {"removed": store.clear()}

    # ------------------------------------------------------------------ #
    @app.post("/api/download")
    def start_download(req: DownloadRequest) -> dict:
        valid = {q.value for q in Quality}
        quality = req.quality if req.quality in valid else "high"
        output_dir = req.output_dir or settings.get("output_dir")

        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, url=req.url, quality=quality, output_dir=output_dir)
        store.add(job)

        dl_job = DownloadJob(
            track=Track(id=job_id, title=req.url, webpage_url=req.url),
            quality=Quality(quality),
            output_dir=output_dir,
            embed_metadata=req.embed_metadata,
            embed_thumbnail=req.embed_thumbnail,
        )

        def run() -> None:
            job.state = "running"
            job.status_text = "Starting"

            def on_progress(status: str, pct: float, bps: float, eta: float) -> None:
                job.status_text = STATUS_TEXT.get(status, status.title())
                job.percent = pct
                job.speed = bps
                job.eta = eta

            with dl_lock:
                result = downloader.download(dl_job, on_progress=on_progress)

            job.elapsed = result.elapsed_seconds
            job.files = result.files
            job.path = result.path
            if result.success:
                job.state = "done"
                job.status_text = "Done"
                job.percent = 100.0
            else:
                job.state = "error"
                job.status_text = "Failed"
                job.error = result.error

        threading.Thread(target=run, daemon=True, name=f"job-{job_id}").start()
        return job.public()

    # ------------------------------------------------------------------ #
    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        from .assets import render

        # Honour the persisted theme so the browser UI opens in the same mode
        # the desktop app uses.
        return render(settings.get("theme"))

    return app


app = create_app()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    argv = list(argv if argv is not None else sys.argv[1:])
    port = PORT
    for i, a in enumerate(argv):
        if a in ("--port", "-p") and i + 1 < len(argv):
            port = int(argv[i + 1])
        elif a.startswith("--port="):
            port = int(a.split("=", 1)[1])

    log.info("EliLain-Music on http://%s:%d", HOST, port)

    def open_browser() -> None:
        import time
        time.sleep(1.2)
        try:
            webbrowser.open(f"http://{HOST}:{port}")
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        uvicorn.run(app, host=HOST, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
