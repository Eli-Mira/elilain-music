"""Wired appearance acceptance: real local artwork, readable palette, quiet motion."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox

from elilain_music.gui.theme import DARK, LIGHT
from elilain_music.gui.window import MainWindow
from elilain_music.web.assets import render


@pytest.fixture
def wired_window(tmp_path, monkeypatch):
    monkeypatch.setattr("elilain_music.gui.settings.CONFIG_FILE", tmp_path / "settings.json")
    monkeypatch.setattr("elilain_music.gui.settings.CONFIG_DIR", tmp_path)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    yield window
    window.close()
    app.processEvents()


def test_lain_artwork_paints_without_network(wired_window):
    from elilain_music.gui.wired import LainPortrait
    portrait = wired_window.findChild(LainPortrait, "lainPortrait")
    assert portrait is not None, "The real Lain portrait must be part of the desktop UI"
    assert portrait.has_artwork
    assert portrait.grab().width() >= 180


def test_wired_motion_can_be_disabled(wired_window):
    control = wired_window.findChild(QCheckBox, "motionToggle")
    assert control is not None, "CRT motion needs an accessible off switch"
    control.setChecked(False)
    assert not wired_window.lain_portrait.motion_enabled


def test_wired_palettes_follow_eli_blue_cyan_references():
    assert DARK.bg_top == "#080d1b"
    assert LIGHT.bg_top == "#eaf0fa"
    assert DARK.accent == "#77dfee"
    assert LIGHT.accent == "#21576d"


def test_web_art_is_local_and_motion_respects_accessibility():
    html = render("dark")
    assert '/art/lain.png' in html
    assert 'prefers-reduced-motion' in html
    assert 'motionToggle' in html
    assert 'SERIAL EXPERIMENTS' in html


def test_artwork_route_returns_actual_png():
    from fastapi.testclient import TestClient

    from elilain_music.web.main import create_app
    with TestClient(create_app()) as client:
        result = client.get("/art/lain.png")
        assert result.status_code == 200
        assert result.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert client.get("/art/missing.png").status_code == 404


def test_queue_row_text_is_not_vertically_clipped(wired_window):
    from elilain_music.engine import DownloadJob, Track
    from tools.render_check import ensure_render_fonts

    ensure_render_fonts()
    row = wired_window._add_row(DownloadJob(track=Track(id="render", title="A readable track")))
    QApplication.instance().processEvents()
    assert row.label.height() >= row.label.fontMetrics().height(), "Queue title was cropped"
    assert row.state_label.height() >= row.state_label.fontMetrics().height()


def test_offscreen_renderer_has_real_glyphs():
    from PySide6.QtGui import QFont, QRawFont

    from tools.render_check import ensure_render_fonts

    app = QApplication.instance() or QApplication([])
    ensure_render_fonts()
    raw = QRawFont.fromFont(QFont("Georgia", 16))
    assert app is not None
    assert raw.isValid() and raw.supportsCharacter("L"), "Screenshot text must be real glyphs"


def test_packaged_art_is_present():
    import elilain_music
    art = Path(elilain_music.__file__).parent / "assets" / "lain.png"
    assert art.is_file()
