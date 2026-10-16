"""Qt Quick frontend. Python owns downloads; QML owns presentation.

A worker is retained until QThread.finished, including cancellation/close.
Queue entries contain data only: clearing a row cannot delete a worker's UI refs.
"""
from __future__ import annotations

import logging
import sys
import uuid
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Property, QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from ..engine import Downloader, DownloadJob, DownloadResult, EngineConfig, Quality, Track
from .settings import Settings
from .theme import DARK, LIGHT
from .wired import ART_DIR

QML_DIR = Path(__file__).parent / "quick"
log = logging.getLogger("elilain.qml")


class Task(QThread):
    progressed = Signal(str, float, float, float)
    completed = Signal(object)
    crashed = Signal(str)

    def __init__(self, downloader, job, parent=None):
        super().__init__(parent)
        self.downloader = downloader
        self.job = job

    def run(self):
        try:
            raw = self.job.track.webpage_url
            host = urlparse(raw).hostname or ""
            if host == "open.spotify.com" or host.endswith(".spotify.com") or raw.startswith("spotify:"):
                from ..engine.spotify import SpotifyMetadataResolver
                self.progressed.emit("resolving", 0, 0, 0)
                resolved = SpotifyMetadataResolver(deep_search=True).resolve(raw)
                if not resolved.matched_track:
                    raise RuntimeError("No free source found for this Spotify track. Try artist + song title.")
                self.job.track = resolved.matched_track
            if self.isInterruptionRequested():
                self.completed.emit(DownloadResult(self.job, False, error="Cancelled"))
                return
            result = self.downloader.download(self.job, on_progress=self.progressed.emit)
            self.completed.emit(result)
        except Exception as exc:
            log.exception("download task failed")
            self.crashed.emit(str(exc))


class Controller(QObject):
    preferencesChanged = Signal()
    jobsChanged = Signal()
    busyChanged = Signal()
    errorChanged = Signal()
    messageChanged = Signal()
    safeToClose = Signal()

    def __init__(self, settings=None, downloader_factory=Downloader, parent=None):
        super().__init__(parent)
        self.settings = settings or Settings()
        self._factory = downloader_factory
        self._jobs = []
        self._worker = None
        self._downloader = None
        self._busy = False
        self._closing = False
        self._cancelled = False
        self._error = ""
        self._message = "Ready to connect. Your music stays on this machine."

    @Property("QVariantMap", notify=preferencesChanged)
    def preferences(self):
        return self.settings.as_dict()

    @Property("QVariantMap", notify=preferencesChanged)
    def palette(self):
        return asdict(DARK if self.settings.get("theme") == "dark" else LIGHT)

    @Property("QVariantList", notify=jobsChanged)
    def jobs(self):
        return [dict(row) for row in self._jobs]

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(str, notify=errorChanged)
    def error(self):
        return self._error

    @Property(str, notify=messageChanged)
    def message(self):
        return self._message

    @Property(str, constant=True)
    def artworkBase(self):
        return QUrl.fromLocalFile(str(ART_DIR) + "/").toString()

    @Property(str, constant=True)
    def engineVersion(self):
        return Downloader.version()

    @Property(bool, constant=True)
    def ffmpegAvailable(self):
        return bool(EngineConfig().ffmpeg_bin)

    @Slot(str, "QVariant")
    def setPreference(self, key, value):
        if key not in {"theme", "crt_motion", "quality", "fragments", "embed_metadata", "embed_thumbnail", "overwrite"}:
            return
        self.settings.set(key, value)
        self.settings._sanitize()
        self.settings.save()
        self.preferencesChanged.emit()

    @Slot()
    def toggleTheme(self):
        self.setPreference("theme", "light" if self.settings.get("theme") == "dark" else "dark")

    def _set_error(self, text):
        self._error = text
        self.errorChanged.emit()

    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()

    @Slot(str)
    def startDownload(self, raw):
        raw = raw.strip()
        if self._busy:
            self._set_error("A transfer is still active. Wait for it or stop it first.")
            return
        if not raw:
            self._set_error("Paste a link or enter an artist and song title.")
            return
        if not self.ffmpegAvailable:
            self._set_error("ffmpeg is missing. Audio conversion cannot start.")
            return
        self._set_error("")
        self._cancelled = False
        self._closing = False
        track = Track(id=uuid.uuid4().hex[:12], title=raw, webpage_url=raw)
        job = DownloadJob(track=track, quality=Quality(self.settings.get("quality")),
                          output_dir=self.settings.get("output_dir"),
                          overwrite=self.settings.get("overwrite"),
                          embed_metadata=self.settings.get("embed_metadata"),
                          embed_thumbnail=self.settings.get("embed_thumbnail"))
        self._jobs.insert(0, {"id": track.id, "title": raw, "state": "running", "status": "Connecting",
                              "percent": 0.0, "detail": "Connecting to source…", "path": "", "files": [], "error": ""})
        self.jobsChanged.emit()
        self._downloader = self._factory(EngineConfig(output_dir=job.output_dir, max_parallel_downloads=1,
                                                     max_network_split=self.settings.get("fragments")))
        self._worker = Task(self._downloader, job, self)
        self._worker.progressed.connect(self._progress)
        self._worker.completed.connect(self._completed)
        self._worker.crashed.connect(self._failed)
        # Result is not thread completion: controls remain busy until the latter.
        self._worker.finished.connect(self._thread_finished)
        self._busy = True
        self.busyChanged.emit()
        self._set_message("Connecting to the Wired. Transfer running locally.")
        self._worker.start()

    @Slot(str, float, float, float)
    def _progress(self, status, percent, speed, eta):
        if not self._jobs or self._cancelled:
            return
        labels = {"resolving": "Resolving Spotify", "downloading": "Downloading", "extracting": "Converting",
                  "processing": "Converting", "tagging": "Writing tags", "merging": "Merging", "done": "Finalizing"}
        self._jobs[0].update(status=labels.get(status, status.title()), percent=max(0, min(100, percent)),
                             detail=f"{speed / 1048576:.1f} MB/s · {eta:.0f}s remaining" if speed else labels.get(status, status.title()))
        self.jobsChanged.emit()

    @Slot(object)
    def _completed(self, result):
        row = self._jobs[0]
        if self._cancelled:
            row.update(state="cancelled", status="Cancelled", detail="Transfer stopped.")
        else:
            candidates = result.files or ([result.path] if result.path else [])
            files = list(dict.fromkeys(str(Path(p)) for p in candidates if Path(p).is_file() and Path(p).stat().st_size > 0))
            success = result.success and bool(files)
            detail = result.error or "The source returned no audio file."
            if success:
                detail = f"{len(files)} file{'s' if len(files) != 1 else ''} saved · {result.elapsed_seconds:.1f}s"
            row.update(title=result.job.track.display, state="done" if success else "error",
                       status="Saved" if success else "Failed", percent=100 if success else row["percent"],
                       path=files[0] if files else "", files=files, error="" if success else detail, detail=detail)
            if not success:
                self._set_error(detail)
        self.jobsChanged.emit()
        self._set_message(row["detail"])

    @Slot(str)
    def _failed(self, error):
        self._jobs[0].update(state="cancelled" if self._cancelled else "error",
                             status="Cancelled" if self._cancelled else "Failed", error=error, detail=error)
        if not self._cancelled:
            self._set_error(error)
        self.jobsChanged.emit()
        self._set_message("Transfer stopped." if self._cancelled else error)

    @Slot()
    def _thread_finished(self):
        worker = self._worker
        self._worker = None
        self._downloader = None
        if worker:
            worker.deleteLater()
        self._busy = False
        self.busyChanged.emit()
        if self._closing:
            self.safeToClose.emit()

    @Slot()
    def stop(self):
        if self._worker:
            self._cancelled = True
            self._worker.requestInterruption()
            self._downloader.cancel_all()
            self._set_message("Stopping safely… waiting for the transfer to release its files.")
            if self._jobs:
                self._jobs[0].update(status="Stopping", detail="Waiting for the worker to finish…")
                self.jobsChanged.emit()

    @Slot()
    def clearFinished(self):
        self._jobs = [row for row in self._jobs if row["state"] == "running"]
        self.jobsChanged.emit()

    @Slot(result=bool)
    def requestClose(self):
        if self._busy:
            self._closing = True
            self.stop()
            return False
        self.settings.save()
        return True

    @Slot()
    def dismissError(self):
        self._set_error("")

    @Slot()
    def openFolder(self):
        path = Path(self.settings.get("output_dir"))
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot(QUrl)
    def chooseDestination(self, url):
        path = url.toLocalFile()
        if path and Path(path).is_dir():
            self.settings.set("output_dir", path)
            self.settings.save()
            self.preferencesChanged.emit()


def create_engine(controller):
    # Basic allows full customization; native styles reject custom backgrounds.
    QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"backend": controller})
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("QML frontend could not load; see the Qt diagnostics above")
    engine._controller = controller  # Keep Python object alive as long as QML.
    return engine


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setApplicationName("EliLain-Music")
    app.setOrganizationName("EliLain")
    app.setWindowIcon(QIcon(str(ART_DIR / "lain.ico")))
    controller = Controller()
    engine = create_engine(controller)
    result = app.exec()
    # QML closes only after safeToClose; no QThread is destroyed running.
    del engine
    return result
