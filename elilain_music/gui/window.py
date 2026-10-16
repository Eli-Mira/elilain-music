"""Lain-themed PySide6 dashboard."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..engine import Downloader, DownloadJob, DownloadResult, EngineConfig, Quality, Track
from .settings import Settings
from .theme import get_theme
from .wired import ART_DIR, WiredSidebar

log = logging.getLogger("elilain.gui")

AUDIO_EXT = {".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav", ".aac", ".webm"}

STATUS_STYLE = {
    "queued":    ("Queued",    "text_dim"),
    "downloading": ("Downloading", "signal"),
    "extracting": ("Converting",  "signal"),
    "processing": ("Converting",  "signal"),
    "tagging":   ("Tagging",    "signal"),
    "merging":   ("Merging",    "signal"),
    "done":      ("Done",       "ok"),
    "error":     ("Failed",     "err"),
    "cancelled": ("Cancelled",  "warn"),
}


def human_bytes(n: float) -> str:
    if not n:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def human_eta(seconds: float) -> str:
    if not seconds or seconds < 0:
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


class DownloadWorker(QThread):
    """Runs one Downloader call off the UI thread."""

    progress = Signal(str, float, float, float)   # status, pct, bps, eta
    finished = Signal(object)                      # DownloadResult
    failed = Signal(str)

    def __init__(self, downloader: Downloader, job: DownloadJob, parent=None) -> None:
        super().__init__(parent)
        self._downloader = downloader
        self._job = job

    def run(self) -> None:  # noqa: D102
        try:
            result = self._downloader.download(self._job, on_progress=self._on_progress)
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            log.exception("worker crashed")
            self.failed.emit(str(exc))

    @Slot(str, float, float, float)
    def _on_progress(self, status: str, pct: float, bps: float, eta: float) -> None:
        self.progress.emit(status, pct, bps, eta)


class QueueItem:
    """One row's worth of state."""

    def __init__(self, label: QLabel, state: QLabel, speed: QLabel,
                 track: Track, job: DownloadJob) -> None:
        self.label = label
        self.state_label = state
        self.speed_label = speed
        self.track = track
        self.job = job
        self.state = "queued"
        self.state_text = "Queued"
        self.speed = 0.0
        self.path = ""
        self.result: DownloadResult | None = None
        self.item = None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.theme = get_theme()

        self._downloader: Downloader | None = None
        self._worker: DownloadWorker | None = None
        self._rows: list[QueueItem] = []
        self._pending: list[DownloadJob] = []
        self._current_row: QueueItem | None = None

        self.setWindowTitle("EliLain-Music · Wired Sound Terminal")
        self.setWindowIcon(QIcon(str(ART_DIR / "lain.ico")))
        self.setMinimumSize(1120, 760)
        self.resize(1280, 860)

        self._build()
        self._restore_settings()

        self.theme.themeChanged.connect(self._apply_theme)
        self._apply_theme(self.theme.mode)

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._tick_status)

        self._log("Ready. yt-dlp " + Downloader.version() + " · ffmpeg " +
                  ("found" if self._ffmpeg_ok() else "MISSING — audio conversion will fail"))
        if not self._ffmpeg_ok():
            self._log("ffmpeg was not found. Install it or extraction will fail.", "err")

    # ================================================================== #
    # construction
    # ================================================================== #
    def _build(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(18, 18, 18, 14)
        shell.setSpacing(22)
        self.wired_sidebar = WiredSidebar()
        self.lain_portrait = self.wired_sidebar.portrait
        shell.addWidget(self.wired_sidebar)
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)
        shell.addLayout(outer, 1)

        outer.addLayout(self._build_header())

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_input_card())
        split.addWidget(self._build_queue_card())
        split.setSizes([250, 340])
        outer.addWidget(split, 1)

        outer.addWidget(self._build_footer())

        self.setStatusBar(QStatusBar())
        self.status_label = QLabel("Idle")
        self.statusBar().addWidget(self.status_label)

    # ------------------------------------------------------------------ #
    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(0)
        brand = QLabel("EliLain / Music")
        brand.setObjectName("brand")
        tag = QLabel("LAYER : SOUND  /  LOCAL AUDIO ARCHIVE")
        tag.setObjectName("tagline")
        left.addWidget(brand)
        left.addWidget(tag)
        row.addLayout(left)
        row.addStretch(1)
        self.wired_stamp = QLabel("WIRED / DARK")
        self.wired_stamp.setObjectName("wiredStamp")
        row.addWidget(self.wired_stamp)

        self.btn_theme = QPushButton("Light")
        self.btn_theme.setObjectName("secondary")
        self.btn_theme.setToolTip("Switch between dark and light (Ctrl+T)")
        self.btn_theme.clicked.connect(self.theme.toggle_theme)
        row.addWidget(self.btn_theme)

        btn_open = QPushButton("Open folder")
        btn_open.setObjectName("secondary")
        btn_open.clicked.connect(self._open_output)
        row.addWidget(btn_open)

        return row

    def _build_input_card(self) -> QWidget:
        card = QGroupBox("01 / SOURCE CONNECTION")
        grid = QVBoxLayout(card)
        grid.setSpacing(10)

        # --- URL row
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText(
            "Paste a YouTube / YouTube Music / SoundCloud / Spotify link, or type a search…"
        )
        self.url_input.returnPressed.connect(self._start)
        url_row.addWidget(self.url_input, 1)

        self.btn_go = QPushButton("Download")
        self.btn_go.setMinimumWidth(120)
        self.btn_go.clicked.connect(self._start)
        url_row.addWidget(self.btn_go)

        self.btn_cancel = QPushButton("Stop")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        url_row.addWidget(self.btn_cancel)
        grid.addLayout(url_row)

        # --- options row
        opts = QHBoxLayout()
        opts.setSpacing(14)

        opts.addWidget(self._labelled("Quality", self._build_quality()))
        opts.addWidget(self._labelled("Parallel", self._build_spin(1, 8, 4, "_spin_parallel")))
        opts.addWidget(self._labelled("Fragments", self._build_spin(1, 16, 8, "_spin_fragments")))
        opts.addStretch(1)
        grid.addLayout(opts)
        opts = QHBoxLayout()
        opts.setSpacing(14)

        self.chk_meta = QCheckBox("Tags")
        self.chk_meta.setChecked(True)
        self.chk_meta.setToolTip("Write artist/title/album into the file")
        self.chk_art = QCheckBox("Cover")
        self.chk_art.setChecked(True)
        self.chk_art.setToolTip("Embed the thumbnail as cover art")
        self.chk_over = QCheckBox("Overwrite")
        self.chk_over.setToolTip("Replace files that already exist")
        for c in (self.chk_meta, self.chk_art, self.chk_over):
            opts.addWidget(c)

        opts.addStretch(1)
        self.btn_dest = QPushButton("Destination…")
        self.btn_dest.setObjectName("secondary")
        self.btn_dest.clicked.connect(self._pick_output)
        opts.addWidget(self.btn_dest)

        grid.addLayout(opts)

        # --- log
        from PySide6.QtWidgets import QTextEdit
        self.log_box = QTextEdit()
        self.log_box.setObjectName("log")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120)
        grid.addWidget(self.log_box)

        return card

    def _build_quality(self) -> QComboBox:
        cb = QComboBox()
        for q in Quality:
            cb.addItem(q.label, q.value)
        cb.setCurrentIndex(2)
        cb.setToolTip("Higher presets re-encode with ffmpeg; Best keeps the source codec")
        self._quality = cb
        return cb

    def _build_spin(self, lo: int, hi: int, val: int, name: str) -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(val)
        sb.setFixedWidth(64)
        setattr(self, name, sb)
        return sb

    def _labelled(self, text: str, widget: QWidget) -> QWidget:
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)
        lab = QLabel(text)
        lab.setObjectName("faint")
        col.addWidget(lab)
        col.addWidget(widget)
        return box

    def _build_queue_card(self) -> QWidget:
        card = QGroupBox("02 / TRANSFER QUEUE")
        col = QVBoxLayout(card)
        col.setSpacing(8)

        self.queue = QListWidget()
        self.queue.setSelectionMode(QListWidget.ExtendedSelection)
        col.addWidget(self.queue, 1)
        self.empty_label = QLabel("NO SIGNAL YET\nPaste a link above to start your local archive.")
        self.empty_label.setObjectName("dim")
        self.empty_label.setAlignment(Qt.AlignCenter)
        col.addWidget(self.empty_label)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        row.addWidget(self.bar, 1)

        self.pct_label = QLabel("0%")
        self.pct_label.setObjectName("dim")
        self.pct_label.setMinimumWidth(42)
        row.addWidget(self.pct_label)

        self.rate_label = QLabel("")
        self.rate_label.setObjectName("dim")
        self.rate_label.setMinimumWidth(180)
        row.addWidget(self.rate_label)

        btn_clear = QPushButton("Clear finished")
        btn_clear.setObjectName("secondary")
        btn_clear.clicked.connect(self._clear_finished)
        row.addWidget(btn_clear)

        col.addLayout(row)
        return card

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self.path_label = QLabel("")
        self.path_label.setObjectName("faint")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.path_label, 1)

        btn_clear_all = QPushButton("Clear all")
        btn_clear_all.setObjectName("secondary")
        btn_clear_all.clicked.connect(self._clear_all)
        row.addWidget(btn_clear_all)

        return bar

    # ================================================================== #
    # theme
    # ================================================================== #
    @Slot(str)
    def _apply_theme(self, mode: str) -> None:
        app = QApplication.instance()
        if app:
            app.setStyleSheet(self.theme.stylesheet())
            pal = app.palette()
            p = self.theme.palette
            pal.setColor(QPalette.Window, QColor(p.bg_top))
            pal.setColor(QPalette.WindowText, QColor(p.text))
            pal.setColor(QPalette.Base, QColor(p.surface_alt))
            pal.setColor(QPalette.Text, QColor(p.text))
            pal.setColor(QPalette.Highlight, QColor(p.accent))
            pal.setColor(QPalette.HighlightedText, QColor(p.accent_text))
            pal.setColor(QPalette.PlaceholderText, QColor(p.text_faint))
            app.setPalette(pal)
        self.btn_theme.setText("Real World" if mode == "dark" else "Wired")
        self.wired_stamp.setText("WIRED / DARK" if mode == "dark" else "REAL WORLD / LIGHT")
        for row in self._rows:
            self._paint_row(row)

    # ================================================================== #
    # settings
    # ================================================================== #
    def _restore_settings(self) -> None:
        s = self.settings
        self.theme.set_mode(s.get("theme"))
        self.wired_sidebar.motion_toggle.setChecked(bool(s.get("crt_motion")))
        idx = self.quality_combo().findData(s.get("quality"))
        if idx >= 0:
            self.quality_combo().setCurrentIndex(idx)
        self.spin_parallel().setValue(int(s.get("parallel")))
        self.spin_fragments().setValue(int(s.get("fragments")))
        self.dest_path = str(s.get("output_dir"))
        self.chk_meta.setChecked(bool(s.get("embed_metadata")))
        self.chk_art.setChecked(bool(s.get("embed_thumbnail")))
        self.chk_over.setChecked(bool(s.get("overwrite")))

    def _save_settings(self) -> None:
        s = self.settings
        s.update(
            theme=self.theme.mode,
            crt_motion=self.wired_sidebar.motion_toggle.isChecked(),
            quality=self.quality_combo().currentData(),
            parallel=self.spin_parallel().value(),
            fragments=self.spin_fragments().value(),
            output_dir=self.dest_path,
            embed_metadata=self.chk_meta.isChecked(),
            embed_thumbnail=self.chk_art.isChecked(),
            overwrite=self.chk_over.isChecked(),
            last_inputs=[self.url_input.text()] + list(s.get("last_inputs"))[:19],
        )
        s.save()

    # ================================================================== #
    # actions
    # ================================================================== #
    @Slot()
    def _start(self) -> None:
        raw = self.url_input.text().strip()
        if not raw:
            QMessageBox.information(self, "Nothing to do", "Paste a link or type a search first.")
            self.url_input.setFocus()
            return

        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "Wait for the current download or press Stop first.")
            return

        job = self._build_job(raw)
        self._enqueue(job)
        self._save_settings()

    def _build_job(self, raw: str) -> DownloadJob:
        quality = Quality(self.quality_combo().currentData())
        track = Track(id="", title=raw, webpage_url=raw)

        is_spotify = raw.lower().startswith("spotify:") or "spotify.com" in raw.lower()
        if is_spotify:
            resolved = self._resolve_spotify(raw)
            if resolved is None:
                track = Track(id="", title=raw, webpage_url=f"ytsearch1:{raw}", tags=["spotify-unresolved"])
            else:
                track = resolved

        return DownloadJob(
            track=track,
            quality=quality,
            output_dir=self.dest_path,
            overwrite=self.chk_over.isChecked(),
            embed_metadata=self.chk_meta.isChecked(),
            embed_thumbnail=self.chk_art.isChecked(),
        )

    def _resolve_spotify(self, raw: str) -> Track | None:
        from ..engine.spotify import SpotifyMetadataResolver
        self._log("Resolving Spotify link…")
        try:
            res = SpotifyMetadataResolver(deep_search=True).resolve(raw)
        except Exception as exc:  # noqa: BLE001
            self._log(f"Spotify resolve failed: {exc}", "err")
            return None
        if res.matched_track:
            self._log(f"Matched {res.display} → {res.matched_track.source.value}")
            return res.matched_track
        self._log(f"No free source found for {res.display}", "warn")
        return None

    def _enqueue(self, job: DownloadJob) -> None:
        self._add_row(job)
        self._pending.append(job)
        self._pump()

    def _pump(self) -> None:
        """Start the next pending job if the worker slot is free."""
        if self._worker and self._worker.isRunning():
            return
        if not self._pending:
            self._set_idle()
            return

        job = self._pending.pop(0)
        row = next((r for r in self._rows if r.job is job), None)
        self._current_row = row

        config = EngineConfig(
            max_parallel_downloads=1,
            max_network_split=self.spin_fragments().value(),
            output_dir=self.dest_path,
        )
        self._downloader = self._downloader or Downloader(config)
        self._downloader.config = config

        self.btn_go.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self._status_timer.start(250)

        self._worker = DownloadWorker(self._downloader, job, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    @Slot(str, float, float, float)
    def _on_progress(self, status: str, pct: float, bps: float, eta: float) -> None:
        row = self._current_row
        if row:
            row.state = status
            row.speed = bps
            self._paint_row(row)
        self.bar.setValue(int(max(0, min(100, pct))))
        self.pct_label.setText(f"{pct:.0f}%")
        self.rate_label.setText(f"{human_bytes(bps)}/s  ·  ETA {human_eta(eta)}")

    @Slot(object)
    def _on_finished(self, result: DownloadResult) -> None:
        self._status_timer.stop()
        row = self._current_row
        if row:
            row.result = result
            row.path = result.path
            row.state = "done" if result.success else "error"
            self._paint_row(row)

        if result.success:
            n = len(result.files) or 1
            self._log(f"✓ {result.job.track.display} — {human_eta(result.elapsed_seconds)}"
                      + (f" ({n} files)" if n > 1 else ""), "ok")
            self.path_label.setText(result.path)
            if row:
                self.path_label.setText(f"{row.label.text()}  →  {result.path}")
        else:
            self._log(f"✗ {result.job.track.display} — {result.error}", "err")

        self._current_row = None
        self._pump()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._status_timer.stop()
        self._log(f"Worker crashed: {message}", "err")
        self._current_row = None
        self._pump()

    @Slot()
    def _cancel(self) -> None:
        if self._downloader:
            n = self._downloader.cancel_all()
            self._log(f"Stop requested — {n} active download(s) cancelled.", "warn")
        self._pending.clear()
        self._downloader = None
        self.btn_cancel.setEnabled(False)
        self.btn_go.setEnabled(True)
        self.bar.setValue(0)
        self.rate_label.setText("")
        self._set_idle()

    # ================================================================== #
    # queue rendering
    # ================================================================== #
    def _add_row(self, job: DownloadJob) -> QueueItem:
        host = QWidget()
        host.setObjectName("queueRow")
        layout = QHBoxLayout(host)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        label = QLabel(job.track.display)
        label.setToolTip(job.track.webpage_url)
        layout.addWidget(label, 1)

        state = QLabel("queued")
        state.setMinimumWidth(92)
        state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(state)

        speed = QLabel("")
        speed.setObjectName("faint")
        speed.setMinimumWidth(160)
        speed.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(speed)

        item = QListWidgetItem()
        item.setSizeHint(QSize(host.sizeHint().width(), max(48, host.sizeHint().height())))
        self.queue.addItem(item)
        self.queue.setItemWidget(item, host)

        row = QueueItem(label, state, speed, job.track, job)
        row.item = item
        self._rows.append(row)
        self.empty_label.setVisible(False)
        self._paint_row(row)
        self.queue.scrollToItem(item)
        return row

    def _paint_row(self, row: QueueItem) -> None:
        p = self.theme.palette
        text, token = STATUS_STYLE.get(row.state, (row.state.title(), "text_dim"))
        row.state_text = text
        row.state_label.setText(text)
        colour = {
            "text_dim": p.text_dim, "signal": p.signal, "ok": p.ok,
            "warn": p.warn, "err": p.err,
        }.get(token, p.text_dim)
        row.state_label.setStyleSheet(
            f"color: {colour}; font-weight: 600; font-size: 11px;"
        )
        row.speed_label.setText(human_bytes(row.speed) + "/s" if row.speed else "")
        if row.path:
            row.label.setToolTip(row.path)

    @Slot()
    def _clear_finished(self) -> None:
        keep = [r for r in self._rows if r.state not in ("done", "error", "cancelled")]
        if len(keep) == len(self._rows):
            self._log("Nothing finished to clear.")
            return
        removed = len(self._rows) - len(keep)
        self._rows = keep
        self._rebuild_queue()
        self._log(f"Cleared {removed} finished item(s).")

    @Slot()
    def _clear_all(self) -> None:
        if self._worker and self._worker.isRunning():
            self._cancel()
        self._rows.clear()
        self._pending.clear()
        self._rebuild_queue()
        self.bar.setValue(0)
        self.pct_label.setText("0%")
        self.rate_label.setText("")
        self.path_label.setText("")

    def _rebuild_queue(self) -> None:
        """Re-attach the surviving rows to fresh list items.

        QListWidget takes ownership of item widgets, so clearing the list
        deletes them. Keep the widget refs alive in the rows and re-attach.
        """
        self.queue.clear()
        for r in self._rows:
            item = QListWidgetItem()
            item.setSizeHint(r.label.parentWidget().sizeHint())
            self.queue.addItem(item)
            self.queue.setItemWidget(item, r.label.parentWidget())
            r.item = item
        self.empty_label.setVisible(not self._rows)
        self._repaint_rows()

    def _repaint_rows(self) -> None:
        for r in self._rows:
            self._paint_row(r)

    # ================================================================== #
    # misc
    # ================================================================== #
    @Slot()
    def _tick_status(self) -> None:
        row = self._current_row
        if not row:
            return
        pct = self.bar.value()
        self.status_label.setText(f"{row.label.text()}  ·  {pct}%")

    def _set_idle(self) -> None:
        self._status_timer.stop()
        self.btn_go.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        if not self._pending:
            self.status_label.setText("Idle")

    def _ffmpeg_ok(self) -> bool:
        return bool(EngineConfig().ffmpeg_bin)

    @Slot()
    def _open_output(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        path = Path(self.dest_path)
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot()
    def _pick_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose destination folder", self.dest_path)
        if d:
            self.dest_path = d
            self._log(f"Destination → {d}")
            self._save_settings()

    def _log(self, message: str, level: str = "info") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"ok": "✓", "err": "✗", "warn": "!"}.get(level, "·")
        self.log_box.append(f"{stamp}  {prefix} {message}")
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker and self._worker.isRunning():
            if self._downloader:
                self._downloader.cancel_all()
            self._worker.wait(3000)
        self._save_settings()
        super().closeEvent(event)

    # --- accessors -----------------------------------------------------
    def quality_combo(self) -> QComboBox:
        return self._quality

    def spin_parallel(self) -> QSpinBox:
        return self._spin_parallel

    def spin_fragments(self) -> QSpinBox:
        return self._spin_fragments


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("EliLain-Music")
    app.setOrganizationName("EliLain")
    app.setStyle("Fusion")

    theme = get_theme()
    app.setStyleSheet(theme.stylesheet())

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
