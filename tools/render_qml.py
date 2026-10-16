"""Exercise/render the real Qt Quick window, never touching user preferences."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QPointF, qInstallMessageHandler
from PySide6.QtGui import QFont
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from elilain_music.gui.qml import Controller, create_engine
from elilain_music.gui.settings import Settings
from tools.render_check import ensure_render_fonts


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ["TMPDIR"])
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    ensure_render_fonts()
    app.setFont(QFont("Segoe UI", 10))
    messages = []
    previous = qInstallMessageHandler(lambda _t, _c, message: messages.append(message))
    settings = Settings(out / "render-settings.json")
    settings.set("theme", "dark")
    settings.set("crt_motion", False)
    controller = Controller(settings)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    reports = []
    for width, height in ((1340, 940), (1120, 820)):
        window.resize(width, height)
        for mode in ("dark", "light"):
            controller.setPreference("theme", mode)
            QTest.qWait(180)
            app.processEvents()
            image = window.grabWindow()
            assert not image.isNull(), "Qt Quick must render a real image"
            path = out / f"qml-{mode}-{width}.png"
            assert image.save(str(path))
            controls = ["sourceInput", "downloadButton", "stopButton", "qualityControl", "fragmentControl",
                        "destinationButton", "clearButton", "themeButton", "folderButton", "wiredBanner", "motionToggle", "artCredit"]
            bounds = []
            for name in controls:
                item = window.findChild(QQuickItem, name)
                assert item, name
                pos = item.mapToScene(QPointF(0, 0))
                assert pos.x() >= 0 and pos.y() >= 0, (name, pos)
                assert pos.x() + item.width() <= width + 1 and pos.y() + item.height() <= height + 1, (name, pos, item.size())
                bounds.append({"name": name, "x": pos.x(), "y": pos.y(), "width": item.width(), "height": item.height()})
            pixel = image.pixelColor(4, 4).name()
            assert pixel == controller.palette["bg_top"], (pixel, controller.palette["bg_top"])
            reports.append({"mode": mode, "size": [width, height], "screenshot": str(path), "background": pixel, "controls": bounds})
    # Repeated real palette changes must not recreate the window or lose source input.
    source = window.findChild(QQuickItem, "sourceInput")
    source.setProperty("text", "retained input")
    for _ in range(10):
        controller.toggleTheme()
        app.processEvents()
    assert source.property("text") == "retained input"
    assert len(engine.rootObjects()) == 1
    assert not messages, "QML diagnostics: " + "\n".join(messages)
    window.close()
    app.processEvents()
    qInstallMessageHandler(previous)
    report = {"renders": reports, "qml_messages": messages, "theme_toggles": 10}
    (out / "qml-render-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"screenshots": [r["screenshot"] for r in reports], "qml_diagnostics": messages, "theme_toggles": 10, "overflow": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
