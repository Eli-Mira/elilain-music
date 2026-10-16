"""Native QML acceptance tests, no network or user settings writes."""
from __future__ import annotations

import importlib.util
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    from tools.render_check import ensure_render_fonts
    ensure_render_fonts()
    from PySide6.QtGui import QFont
    app.setFont(QFont("Segoe UI", 10))
    return app


def test_qml_frontend_loads_real_window(qapp, tmp_path):
    assert importlib.util.find_spec("elilain_music.gui.qml") is not None, "Desktop needs a real QML frontend"
    from elilain_music.gui.qml import Controller, create_engine
    from elilain_music.gui.settings import Settings
    controller = Controller(settings=Settings(tmp_path / "settings.json"))
    engine = create_engine(controller)
    qapp.processEvents()
    assert engine.rootObjects(), "QML must compile and instantiate"
    window = engine.rootObjects()[0]
    assert window.isVisible()
    assert window.findChild(__import__("PySide6.QtCore", fromlist=["QObject"]).QObject, "sourceInput") is not None
    window.close()
    qapp.processEvents()


def test_qml_download_bridge_runs_off_ui_thread(qapp, tmp_path):
    assert importlib.util.find_spec("elilain_music.gui.qml") is not None, "QML needs a Python engine bridge"
    import threading

    from PySide6.QtCore import QEventLoop, QTimer

    from elilain_music.engine import DownloadResult
    from elilain_music.gui.qml import Controller
    from elilain_music.gui.settings import Settings

    called = []
    class TestDownloader:
        def __init__(self, config):
            self.config = config
        def download(self, job, on_progress):
            called.append(threading.get_ident())
            on_progress("downloading", 42, 1024, 2)
            audio = tmp_path / "fixture.mp3"
            audio.write_bytes(b"unit-test-output-not-real-audio")
            return DownloadResult(job, True, str(audio), files=[str(audio)])
        def cancel_all(self):
            return 0

    controller = Controller(settings=Settings(tmp_path / "settings.json"), downloader_factory=TestDownloader)
    loop = QEventLoop()
    controller.busyChanged.connect(lambda: loop.quit() if not controller.busy else None)
    controller.startDownload("https://soundcloud.com/test/unit-test")
    assert controller.busy
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert not controller.busy
    assert called and called[0] != threading.get_ident()
    assert controller.jobs[0]["state"] == "done"
    assert controller.jobs[0]["files"] == [str(tmp_path / "fixture.mp3")]
    controller.clearFinished()
    assert controller.jobs == []


def test_small_window_keeps_every_sidebar_control_inside(qapp, tmp_path):
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from elilain_music.gui.qml import Controller, create_engine
    from elilain_music.gui.settings import Settings

    controller = Controller(Settings(tmp_path / "settings.json"))
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    for width, height in ((1120, 820), (1340, 940)):
        window.resize(width, height)
        QTest.qWait(100)
        motion = window.findChild(QQuickItem, "motionToggle")
        credit = window.findChild(QQuickItem, "artCredit")
        bottom = max(motion.mapToScene(QPointF(0, motion.height())).y(), credit.mapToScene(QPointF(0, credit.height())).y())
        assert bottom <= height - 24 - (16 if height < 880 else 20), f"Sidebar spills into card padding: {bottom} at {width}x{height}"
    window.close()

