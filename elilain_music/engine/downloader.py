"""Download engine built on yt-dlp's Python API.

Why the API and not the CLI: yt-dlp only writes human-readable progress lines
when stdout is a TTY. Under `subprocess.PIPE` it emits *nothing*, so scraping
`[download] 42.1% ...` out of a subprocess gives you a progress bar frozen at
0% forever. The Python API exposes `progress_hooks` with structured
(downloaded_bytes, total_bytes, speed, eta) — real numbers, no parsing.

Design:
* one Downloader owns a config; N worker threads pull from a job queue
* each job gets its own YoutubeDL instance (they are not thread-safe)
* in-flight jobs are registered so cancel_all() can stop them
* progress is coalesced (see _ProgressThrottle) because yt-dlp fires hooks
  per network chunk — unthrottled that's ~90 signals/sec and floods a Qt GUI
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .engine_config import EngineConfig
from .models import DownloadJob, DownloadResult

log = logging.getLogger("elilain.downloader")

AUDIO_SUFFIXES = ("mp3", "m4a", "flac", "opus", "ogg", "wav", "aac", "webm")

# (status, percent, bytes_per_second, eta_seconds)
ProgressFn = Callable[[str, float, float, float], None]


class CancelledError(Exception):
    """Raised inside a progress hook when the user cancels."""


class _Active:
    """Cancellation handle for one in-flight job."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> bool:
        if self._event.is_set():
            return False
        self._event.set()
        return True


class _ProgressThrottle:
    """Rate-limits progress callbacks to roughly 12/sec.

    yt-dlp invokes the hook per network chunk; at 3 MB/s with 32 KB chunks
    that is ~90 callbacks/sec. Forwarded raw into a Qt signal it saturates
    the event loop and the window stops repainting.
    """

    MIN_INTERVAL = 0.08

    def __init__(self, fn: ProgressFn | None) -> None:
        self._fn = fn
        self._last = 0.0
        self._pending: tuple | None = None
        self._lock = threading.Lock()

    def push(self, status: str, pct: float, speed: float, eta: float) -> None:
        if self._fn is None:
            return
        now = time.monotonic()
        with self._lock:
            if now - self._last < self.MIN_INTERVAL:
                self._pending = (status, pct, speed, eta)
                return
            self._last = now
            self._pending = None
        self._emit(status, pct, speed, eta)

    def force(self, status: str, pct: float, speed: float, eta: float) -> None:
        """Emit now, ignoring the throttle — used for discrete state changes."""
        if self._fn is None:
            return
        with self._lock:
            self._last = time.monotonic()
            self._pending = None
        self._emit(status, pct, speed, eta)

    def flush(self) -> None:
        """Emit the most recent suppressed payload, if any."""
        if self._fn is None:
            return
        with self._lock:
            payload = self._pending
            self._pending = None
        if payload:
            self._emit(*payload)

    def _emit(self, *args) -> None:
        try:
            self._fn(*args)  # type: ignore[misc]
        except Exception:  # noqa: BLE001 — a bad callback must not kill a download
            log.debug("progress callback raised", exc_info=True)


class Downloader:
    """Thread-safe facade over yt-dlp. One instance = one config."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()
        self._lock = threading.RLock()
        self._active: dict[int, _Active] = {}
        self._cancelled = False

    # ------------------------------------------------------------------ #
    @staticmethod
    def version() -> str:
        try:
            from yt_dlp.version import __version__
            return __version__
        except Exception:  # noqa: BLE001
            return "unknown"

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    # ------------------------------------------------------------------ #
    # cancellation
    # ------------------------------------------------------------------ #
    def cancel_all(self) -> int:
        """Abort every in-flight download. Returns how many were stopped."""
        with self._lock:
            self._cancelled = True
            actives = list(self._active.values())
        return sum(1 for a in actives if a.cancel())

    def reset(self) -> None:
        with self._lock:
            self._cancelled = False

    # ------------------------------------------------------------------ #
    # single download
    # ------------------------------------------------------------------ #
    def download(
        self,
        job: DownloadJob,
        on_progress: ProgressFn | None = None,
    ) -> DownloadResult:
        """Download one track, or every entry of a playlist URL."""
        if self._cancelled:
            return DownloadResult(job, False, error="Cancelled before start.")

        try:
            import yt_dlp
        except ImportError as exc:
            return DownloadResult(job, False, error=f"yt-dlp is not installed: {exc}")

        output_dir = job.output_dir or self.config.output_dir or str(
            Path.home() / "Music" / "EliLain"
        )
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        active = _Active()
        with self._lock:
            self._active[id(active)] = active

        throttle = _ProgressThrottle(on_progress)
        collected: list[str] = []
        started = time.monotonic()

        def progress_hook(d: dict) -> None:
            if active.cancelled:
                raise CancelledError()
            status = d.get("status")
            if status == "downloading":
                got = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = (got / total * 100.0) if total else 0.0
                throttle.push("downloading", pct, d.get("speed") or 0.0, d.get("eta") or 0)
            elif status == "finished":
                fn = d.get("filename") or ""
                if fn:
                    collected.append(fn)
                throttle.force("extracting", 100.0, 0.0, 0.0)

        def pp_hook(d: dict) -> None:
            if active.cancelled:
                raise CancelledError()
            if d.get("status") == "started":
                name = (d.get("postprocessor") or "").lower()
                if "extract" in name or "audio" in name:
                    throttle.force("processing", 100.0, 0.0, 0.0)
                elif any(k in name for k in ("thumbnail", "embed", "metadata")):
                    throttle.force("tagging", 100.0, 0.0, 0.0)

        ydl_opts: dict = {
            "format": job.format_selector,
            "outtmpl": str(Path(output_dir) / job.filename_template),
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [pp_hook],
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": self._is_single_url(job.track.webpage_url),
            "overwrites": job.overwrite,
            "continuedl": not job.overwrite,
            "retries": self.config.retries,
            "fragment_retries": self.config.fragment_retries,
            "socket_timeout": self.config.socket_timeout,
            "concurrent_fragment_downloads": max(1, self.config.max_network_split),
            "windowsfilenames": True,
            "cachedir": str(Path(output_dir) / ".elilain-cache"),
        }

        pps: list[dict] = []
        if job.quality.audio_format:
            # Without this the quality preset is a no-op and you keep the raw
            # .webm stream instead of the requested codec.
            pps.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": job.quality.audio_format,
                "preferredquality": "5",
            })
        if job.embed_metadata:
            pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True})
            if job.embed_thumbnail:
                pps.append({"key": "EmbedThumbnail"})
        if pps:
            ydl_opts["postprocessors"] = pps

        if self.config.cookie_file:
            ydl_opts["cookiefile"] = self.config.cookie_file
        if self.config.proxy:
            ydl_opts["proxy"] = self.config.proxy
        if self.config.ffmpeg_bin:
            # yt-dlp wants the DIRECTORY containing ffmpeg, not the exe itself
            ydl_opts["ffmpeg_location"] = str(Path(self.config.ffmpeg_bin).parent)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([job.track.webpage_url])
        except CancelledError:
            return DownloadResult(
                job, False, error="Cancelled.",
                elapsed_seconds=time.monotonic() - started, files=collected)
        except Exception as exc:  # noqa: BLE001
            return DownloadResult(
                job, False, error=_clean_error(exc),
                elapsed_seconds=time.monotonic() - started, files=collected)
        finally:
            with self._lock:
                self._active.pop(id(active), None)

        throttle.force("done", 100.0, 0.0, 0.0)

        files = [f for f in collected if Path(f).exists()]
        if not files:
            files = self._find_outputs(output_dir)
        if not files:
            return DownloadResult(
                job, False, error="yt-dlp reported success but no audio file was produced.",
                elapsed_seconds=time.monotonic() - started)

        return DownloadResult(
            job, True,
            path=files[0],
            files=files,
            elapsed_seconds=time.monotonic() - started,
        )

    # ------------------------------------------------------------------ #
    # batch
    # ------------------------------------------------------------------ #
    def download_many(
        self,
        jobs: list[DownloadJob],
        on_progress: Callable[[DownloadJob, str, float, float, float], None] | None = None,
    ) -> list[DownloadResult]:
        """Run jobs across a bounded thread pool, preserving input order."""
        self.reset()
        if not jobs:
            return []

        results: list[DownloadResult | None] = [None] * len(jobs)
        q: queue.Queue[tuple[int, DownloadJob]] = queue.Queue()
        for idx, j in enumerate(jobs):
            q.put((idx, j))

        def worker() -> None:
            while True:
                try:
                    idx, job = q.get_nowait()
                except queue.Empty:
                    return
                cb = None
                if on_progress:
                    def cb(st, pct, spd, eta, _j=job):  # noqa: B023
                        on_progress(_j, st, pct, spd, eta)
                results[idx] = self.download(job, on_progress=cb)

        n = max(1, min(self.config.max_parallel_downloads, len(jobs)))
        threads = [threading.Thread(target=worker, daemon=True, name="elm-dl") for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        out: list[DownloadResult] = []
        for idx, r in enumerate(results):
            if r is None:
                r = DownloadResult(jobs[idx], False, error="Worker exited without a result.")
            out.append(r)
        return out

    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_single_url(url: str) -> bool:
        u = (url or "").strip().lower()
        if not u.startswith(("http://", "https://")):
            return True     # bare search string -> take only the first hit

        # SoundCloud lives under /artist/track AND /artist/sets/playlist, so a
        # bare "soundcloud.com/" prefix match would misread every playlist as a
        # single track. Test the playlist shapes explicitly instead.
        if "/sets/" in u or "/playlist" in u or "?list=" in u:
            return False
        if "soundcloud.com" in u:
            return True
        return any(m in u for m in (
            "/watch", "youtu.be/", "/embed/", "/shorts/", "/live/",
            "open.spotify.com/", "music.youtube.com/",
        ))

    @staticmethod
    def _find_outputs(output_dir: str) -> list[str]:
        out = Path(output_dir)
        if not out.is_dir():
            return []
        found: list[Path] = []
        for suffix in AUDIO_SUFFIXES:
            found.extend(p for p in out.rglob(f"*.{suffix}") if p.is_file())
        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [str(p) for p in found]


def _clean_error(exc: Exception) -> str:
    """Compress yt-dlp's exception into one readable line."""
    if isinstance(exc, CancelledError):
        return "Cancelled."
    msg = (str(exc) or exc.__class__.__name__).strip().replace("\n", " ")
    if len(msg) > 400:
        msg = msg[:200] + " … " + msg[-200:]
    return msg
