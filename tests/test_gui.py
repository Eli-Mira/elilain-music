"""GUI tests — offscreen rendering, theme switching, settings persistence.

Qt is forced onto the offscreen platform so these run headless in CI.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from elilain_music.engine import DownloadJob, Quality, Track  # noqa: E402
from elilain_music.gui.settings import Settings  # noqa: E402
from elilain_music.gui.theme import DARK, LIGHT, ThemeManager, get_theme  # noqa: E402
from elilain_music.gui.window import MainWindow, human_bytes, human_eta  # noqa: E402

URL = "https://youtu.be/abc"


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def win(app, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "elilain_music.gui.settings.CONFIG_FILE", tmp_path / "settings.json"
    )
    monkeypatch.setattr(
        "elilain_music.gui.settings.CONFIG_DIR", tmp_path
    )
    w = MainWindow()
    yield w
    w.close()


def make_job(title: str = "Test", url: str = URL) -> DownloadJob:
    return DownloadJob(track=Track(id="1", title=title, webpage_url=url), quality=Quality.HIGH)


# ==================================================================== #
# formatting helpers
# ==================================================================== #
@pytest.mark.parametrize(
    "n,expected",
    [(0, "—"), (512, "512 B"), (2048, "2.0 KB"), (5 * 1024**2, "5.0 MB"), (3 * 1024**3, "3.0 GB")],
)
def test_human_bytes(n, expected):
    assert human_bytes(n) == expected


@pytest.mark.parametrize(
    "s,expected", [(0, "—"), (5, "5s"), (65, "1m 05s"), (3725, "1h 02m"), (-1, "—")]
)
def test_human_eta(s, expected):
    assert human_eta(s) == expected


# ==================================================================== #
# theme
# ==================================================================== #
def test_theme_manager_is_a_singleton():
    assert ThemeManager.instance() is ThemeManager.instance()
    assert get_theme() is ThemeManager.instance()


def test_both_palettes_define_every_token():
    tokens = {f.name for f in DARK.__dataclass_fields__.values()}
    assert tokens == {f.name for f in LIGHT.__dataclass_fields__.values()}
    # 'name' is the mode label; every other token is a colour
    for pal in (DARK, LIGHT):
        for field_name, value in pal.__dict__.items():
            if field_name == "name":
                continue
            assert isinstance(value, str), f"{pal.name}.{field_name} is not a string"
            if field_name == "glow":
                continue     # rgba() glow, not a hex
            assert value.startswith("#"), f"{pal.name}.{field_name}={value}"
            assert len(value) in (4, 7), f"{pal.name}.{field_name}={value}"


def test_palettes_differ_in_every_visible_token():
    # A light theme must not be a mechanical inversion; these must be distinct.
    for name in ("bg_top", "surface", "text", "accent", "signal"):
        assert getattr(DARK, name) != getattr(LIGHT, name), name


def test_toggle_flips_mode():
    t = get_theme()
    before = t.mode
    t.toggle()
    assert t.mode != before
    t.toggle()
    assert t.mode == before


def test_invalid_mode_falls_back_to_dark():
    t = get_theme()
    t.set_mode("light")
    t.set_mode("chartreuse")
    assert t.mode == "dark"


def test_stylesheet_embeds_palette_values():
    t = get_theme()
    t.set_mode("dark")
    assert DARK.accent in t.stylesheet()
    assert DARK.bg_top in t.stylesheet()
    t.set_mode("light")
    assert LIGHT.accent in t.stylesheet()
    assert LIGHT.bg_top in t.stylesheet()
    t.set_mode("dark")


def test_theme_change_emits_signal(app):
    t = get_theme()
    seen = []
    t.themeChanged.connect(seen.append)
    t.set_mode("light")
    t.set_mode("dark")
    assert seen == ["light", "dark"]


# ==================================================================== #
# settings
# ==================================================================== #
def test_settings_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = Settings(p)
    s.update(theme="light", quality="lossless", parallel=6, output_dir=str(tmp_path))
    assert s.save() is True

    s2 = Settings(p)
    assert s2.get("theme") == "light"
    assert s2.get("quality") == "lossless"
    assert s2.get("parallel") == 6
    assert s2.get("output_dir") == str(tmp_path)


def test_settings_rejects_unknown_keys(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"theme":"dark","bogus":"x"}', encoding="utf-8")
    s = Settings(p)
    assert "bogus" not in s.as_dict()


def test_settings_clamps_out_of_range(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"parallel": 9999, "fragments": -5, "quality":"nope"}', encoding="utf-8")
    s = Settings(p)
    assert 1 <= s.get("parallel") <= 8
    assert s.get("fragments") >= 1
    assert s.get("quality") == "high"


def test_settings_survives_corrupt_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json at all", encoding="utf-8")
    s = Settings(p)
    assert s.get("theme") == "dark"      # defaults, no exception


def test_settings_save_is_atomic(tmp_path):
    p = tmp_path / "s.json"
    s = Settings(p)
    s.save()
    assert p.is_file()
    # no leftover temp files
    assert not list(tmp_path.glob("*.tmp"))


# ==================================================================== #
# window
# ==================================================================== #
def test_window_builds_with_all_controls(win):
    assert win.quality_combo().count() == len(Quality)
    assert win.spin_parallel().minimum() == 1
    assert win.spin_fragments().maximum() == 16
    assert win.btn_go.isEnabled()
    assert not win.btn_cancel.isEnabled()


def test_theme_button_toggles(win):
    before = win.theme.mode
    win.btn_theme.click()
    assert win.theme.mode != before
    win.btn_theme.click()
    assert win.theme.mode == before


def test_adding_rows_and_clearing(win):
    win._clear_all()
    win._add_row(make_job("One"))
    win._add_row(make_job("Two"))
    assert len(win._rows) == 2
    assert win.queue.count() == 2

    win._rows[0].state = "done"
    win._clear_finished()
    assert len(win._rows) == 1

    win._clear_all()
    assert len(win._rows) == 0


def test_row_states_paint(win):
    win._clear_all()
    for state in ("queued", "downloading", "processing", "done", "error"):
        row = win._add_row(make_job(state))
        row.state = state
        win._paint_row(row)
        assert row.state_label.text()


def test_spotify_job_falls_back_to_search(win):
    job = win._build_job("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT")
    # Whether or not resolution succeeds, the job must have a usable URL.
    assert job.track.webpage_url


def test_plain_url_job_keeps_url(win):
    job = win._build_job(URL)
    assert job.track.webpage_url == URL


def test_settings_saved_on_close(win, tmp_path):
    win.quality_combo().setCurrentIndex(4)
    win.close()
    cfg = tmp_path / "settings.json"
    assert cfg.is_file()
    import json
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["quality"] == "lossless"


def test_empty_input_is_refused(win, monkeypatch):
    monkeypatch.setattr("elilain_music.gui.window.QMessageBox.information",
                        staticmethod(lambda *a, **k: None))
    win.url_input.setText("")
    win._start()
    assert win._worker is None      # nothing was launched
