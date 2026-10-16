"""Acceptance for Eli's supplied artwork, not a generic recolour."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from elilain_music.gui.wired import ART_DIR


@pytest.fixture
def redesign_window(tmp_path, monkeypatch):
    from elilain_music.gui.window import MainWindow
    from tools.render_check import ensure_render_fonts
    monkeypatch.setattr("elilain_music.gui.settings.CONFIG_FILE", tmp_path / "settings.json")
    monkeypatch.setattr("elilain_music.gui.settings.CONFIG_DIR", tmp_path)
    app = QApplication.instance() or QApplication([])
    ensure_render_fonts()
    window = MainWindow()
    window.show()
    app.processEvents()
    yield window
    window.close()
    app.processEvents()


def test_requested_portrait_is_used_without_losing_composition():
    source = Path("C:/Users/emadg/AppData/Roaming/Hermes/composer-images/lain_serialexperimentslain_460a5d.jpg")
    if not source.is_file():
        pytest.skip("Private source reference is only available on Eli's machine")
    original = QImage(str(source)).convertToFormat(QImage.Format_RGB32)
    installed = QImage(str(ART_DIR / "lain.png")).convertToFormat(QImage.Format_RGB32)
    assert installed == original, "Main artwork must be Eli's exact square cyan Lain portrait"
