"""Exercise actual QML controls and QThread lifetimes, no network downloads."""
from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFont
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from elilain_music.engine import DownloadResult
from elilain_music.gui.qml import Controller, create_engine
from elilain_music.gui.settings import Settings
from tools.render_check import ensure_render_fonts


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    ensure_render_fonts()
    application.setFont(QFont("Segoe UI", 10))
    return application


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Qt event-loop deadline exceeded"


def click(window, item):
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
    QTest.qWait(20)


def test_real_controls_and_keyboard_shortcuts(app, tmp_path):
    controller = Controller(Settings(tmp_path / "settings.json"))
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    window.requestActivate()
    QTest.qWait(80)
    try:
        source = window.findChild(QQuickItem, "sourceInput")
        source.setProperty("text", "retained source")
        QTest.keyClick(window, Qt.Key_L, Qt.ControlModifier)
        assert source.hasActiveFocus()
        assert source.property("selectedText") == "retained source"
        theme = window.findChild(QQuickItem, "themeButton")
        click(window, theme)
        assert controller.preferences["theme"] == "light"
        assert source.property("text") == "retained source"
        QTest.keyClick(window, Qt.Key_T, Qt.ControlModifier)
        assert controller.preferences["theme"] == "dark"
        quality = window.findChild(QQuickItem, "qualityControl")
        click(window, quality)
        QTest.keyClick(window, Qt.Key_Down)
        QTest.keyClick(window, Qt.Key_Return)
        assert controller.preferences["quality"] == "best"
        fragments = window.findChild(QQuickItem, "fragmentControl")
        fragments.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Up)
        assert controller.preferences["fragments"] == 9
        motion = window.findChild(QQuickItem, "motionToggle")
        click(window, motion)
        assert controller.preferences["crt_motion"] is True
        controller.setPreference("crt_motion", False)
        assert motion.property("checked") is False
        source.setProperty("text", "")
        click(window, window.findChild(QQuickItem, "downloadButton"))
        assert "Paste" in controller.error
        assert not controller.busy
        persisted = Settings(tmp_path / "settings.json")
        assert persisted.get("fragments") == 9
        assert persisted.get("quality") == "best"
    finally:
        window.close()
        app.processEvents()


def test_close_waits_for_actual_thread_finish_without_blocking_gui(app, tmp_path):
    entered = threading.Event()
    release = threading.Event()
    cancelled = []

    class BlockingDownloader:
        def __init__(self, config):
            self.config = config
        def download(self, job, on_progress):
            entered.set()
            release.wait(3)
            return DownloadResult(job, False, error="Cancelled")
        def cancel_all(self):
            cancelled.append(True)
            return 1

    controller = Controller(Settings(tmp_path / "settings.json"), BlockingDownloader)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    try:
        controller.startDownload("offline-lifecycle-fixture")
        wait_until(entered.is_set)
        worker = controller._worker
        window.close()
        app.processEvents()
        assert window.isVisible(), "Close must defer while QThread is running"
        assert controller.busy and worker.isRunning()
        assert cancelled
        controller.clearFinished()
        assert len(controller.jobs) == 1
        controller.toggleTheme()
        assert controller.preferences["theme"] == "light", "GUI remains responsive during cancellation"
        controller.startDownload("must-not-start-another-worker")
        assert controller._worker is worker
        release.set()
        wait_until(lambda: not controller.busy)
        wait_until(lambda: not window.isVisible())
        assert controller._worker is None
        assert controller.jobs[0]["state"] == "cancelled"
        controller.clearFinished()
        assert controller.jobs == []
    finally:
        release.set()
        wait_until(lambda: not controller.busy)
        window.close()
        app.processEvents()


def test_false_success_with_no_output_becomes_visible_error(app, tmp_path):
    class EmptyDownloader:
        def __init__(self, config):
            pass
        def download(self, job, on_progress):
            return DownloadResult(job, True)
        def cancel_all(self):
            return 0

    controller = Controller(Settings(tmp_path / "settings.json"), EmptyDownloader)
    controller.startDownload("offline-empty-output-fixture")
    wait_until(lambda: not controller.busy)
    assert controller.jobs[0]["state"] == "error"
    assert "no audio file" in controller.error
    assert controller.jobs[0]["files"] == []


def test_worker_exception_is_reported_and_controls_unlock(app, tmp_path):
    class FailedDownloader:
        def __init__(self, config):
            pass
        def download(self, job, on_progress):
            raise RuntimeError("fixture source unavailable")
        def cancel_all(self):
            return 0

    controller = Controller(Settings(tmp_path / "settings.json"), FailedDownloader)
    controller.startDownload("offline-failure-fixture")
    wait_until(lambda: not controller.busy)
    assert controller.jobs[0]["state"] == "error"
    assert controller.error == "fixture source unavailable"
    controller.dismissError()
    assert controller.error == ""
    controller.clearFinished()
    assert controller.jobs == []
