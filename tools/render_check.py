"""Render the window offscreen and report actual pixel colours + geometry.

Used to verify the theme really paints (QSS applied, not just returned as a
string) and that nothing is clipped. Run:
    python tools/render_check.py [out_dir]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elilain_music.engine import DownloadJob, Quality, Track  # noqa: E402
from elilain_music.gui.theme import get_theme  # noqa: E402
from elilain_music.gui.window import MainWindow  # noqa: E402


def ensure_render_fonts() -> None:
    """Windows offscreen QPA exposes no system fonts: load local fonts explicitly.

    This is a test-harness workaround, not a runtime UI requirement. The normal
    windows QPA correctly discovers the installed font collection.
    """
    if os.name == "nt" and not QFontDatabase.families():
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf",
                     "consola.ttf", "msgothic.ttc", "YuGothR.ttc"):
            file = fonts / name
            if file.exists():
                QFontDatabase.addApplicationFont(str(file))
    if not QFontDatabase.families():
        raise RuntimeError("No fonts loaded: screenshot text would be missing glyphs")


def hexc(color) -> str:
    return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"


def sample(img, x, y) -> str:
    return hexc(img.pixelColor(x, y))


def report(mode: str, out_dir: Path) -> None:
    app = QApplication.instance() or QApplication([])
    ensure_render_fonts()
    w = MainWindow()
    # Set the mode AFTER construction: MainWindow._restore_settings() loads the
    # persisted theme and would otherwise override a pre-set mode.
    get_theme().set_mode(mode)
    w.resize(1280, 860)
    w.show()
    app.processEvents()

    rows = [
        ("Big Buck Bunny", "https://youtu.be/aaa", "done"),
        ("Never Gonna Give You Up", "https://youtu.be/bbb", "downloading"),
        ("Around the World", "https://soundcloud.com/daftpunk", "processing"),
        ("bad guy", "spotify:track:4cOdK2wGLETKBW3PvgPWqT", "error"),
    ]
    for i, (title, url, state) in enumerate(rows):
        job = DownloadJob(track=Track(id=str(i), title=title, webpage_url=url), quality=Quality.HIGH)
        row = w._add_row(job)
        row.state = state
        if state == "downloading":
            row.speed = 3.4 * 1024 * 1024
    w._rows[0].path = str(Path.home() / "Music" / "EliLain" / "Big Buck Bunny.mp3")
    for r in w._rows:
        w._paint_row(r)

    w.bar.setValue(46)
    w.pct_label.setText("46%")
    w.rate_label.setText("3.4 MB/s  ·  ETA 12s")
    w._log("Ready. yt-dlp " + __import__("elilain_music.engine.downloader", fromlist=["Downloader"]).Downloader.version())
    w._log("Big Buck Bunny — done in 6s", "ok")
    w._log("bad guy — no free source found", "err")
    app.processEvents()

    img = w.grab().toImage()
    png = out_dir / f"elm_{mode}.png"
    img.save(str(png))

    p = get_theme().palette
    print(f"\n=== {mode.upper()} ===")
    print(f"screenshot      : {png}")
    print(f"window size     : {w.width()}x{w.height()}")
    print(f"queue rows      : {w.queue.count()}")
    print(f"log height      : {w.log_box.height()}px (visible={w.log_box.isVisible()})")
    print(f"accent in qss   : {p.accent in get_theme().stylesheet()}")
    print("painted pixels:")
    for name, (x, y) in {
        "window bg      ": (4, 4),
        "input field    ": (300, 120),
        "progress track ": (300, 640),
        "list row area  ": (300, 420),
    }.items():
        print(f"  {name}: {sample(img, x, y)}")
    print("expected tokens:")
    print(f"  bg_top        : {p.bg_top}")
    print(f"  surface_alt   : {p.surface_alt}")
    print(f"  track         : {p.track}")

    # Map geometry into window coordinates; parent-local coordinates prove nothing.
    overflow = []
    for child in w.findChildren(type(w.url_input)) + w.findChildren(QPushButton):
        if not child.isVisible():
            continue
        g = child.rect().translated(child.mapTo(w, QPoint(0, 0)))
        if not w.rect().contains(g):
            overflow.append((child.objectName() or child.__class__.__name__, g))
    print(f"overflow widgets: {len(overflow)}")
    for name, g in overflow[:5]:
        print(f"  {name}: {g}")

    assert not overflow, f"Controls clipped in {mode}: {overflow}"
    assert w.lain_portrait.has_artwork, "Portrait asset failed to load"
    # Closing test windows must not overwrite the user's actual preferences.
    w._save_settings = lambda: None
    w.close()
    del w


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    report("dark", out_dir)
    report("light", out_dir)
    print("\nrender check complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
