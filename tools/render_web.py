"""Render and exercise the real dashboard in isolated Chromium/QtWebEngine.

Run tools/serve_uiqa.py first. No browser profile or user settings are touched.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PySide6.QtCore import Qt, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication


class Page(QWebEnginePage):
    def __init__(self, profile, parent):
        super().__init__(profile, parent)
        self.errors = []

    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.errors.append(f"{source}:{line}: {message}")


def wait_until(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(20)
    assert predicate(), "Chromium event-loop deadline exceeded"


def evaluate(page, script):
    reply = []
    page.runJavaScript(script, lambda value: reply.append(value))
    wait_until(lambda: bool(reply))
    return reply[0]


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    url = (out / "server-url.txt").read_text(encoding="utf-8").strip()
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication([])
    profile = QWebEngineProfile(app)  # Unnamed profile is off-the-record.
    view = QWebEngineView()
    page = Page(profile, view)
    view.setPage(page)
    view.resize(1340, 1100)
    view.show()
    loaded = []
    view.loadFinished.connect(loaded.append)
    view.load(QUrl(url))
    wait_until(lambda: bool(loaded))
    assert loaded[-1], "Real dashboard must load over HTTP"
    wait_until(lambda: evaluate(page, "document.querySelector('#ytdlp').textContent !== '…'"))
    checks = []
    for width, height in ((1340, 1100), (390, 1100), (320, 1100)):
        view.resize(width, height)
        QTest.qWait(100)
        for mode in ("dark", "light"):
            if evaluate(page, "document.documentElement.dataset.theme") != mode:
                evaluate(page, "document.querySelector('#themeBtn').click(); true")
                wait_until(lambda mode=mode: evaluate(page, "document.documentElement.dataset.theme") == mode)
            QTest.qWait(120)
            report = json.loads(evaluate(page, """JSON.stringify({
                theme:document.documentElement.dataset.theme,
                width:innerWidth,
                overflow:document.documentElement.scrollWidth>innerWidth,
                loadedImages:[...document.images].filter(i=>i.complete&&i.naturalWidth>0).length,
                imageCount:document.images.length,
                background:getComputedStyle(document.body).backgroundColor,
                motion:document.documentElement.dataset.motion
            })"""))
            assert not report["overflow"], report
            assert report["loadedImages"] == report["imageCount"] == 3, report
            screenshot = out / f"web-{mode}-{width}.png"
            assert view.grab().save(str(screenshot))
            checks.append({**report, "screenshot": str(screenshot)})
    # Submit validation happens in actual Chromium, not by string inspection.
    evaluate(page, "document.querySelector('#url').value=''; document.querySelector('#go').click(); true")
    assert "Paste" in evaluate(page, "document.querySelector('#source-error').textContent")
    assert evaluate(page, "document.querySelector('#url').getAttribute('aria-invalid')") == "true"
    assert evaluate(page, "document.activeElement.id") == "url"
    evaluate(page, "document.querySelector('#motionToggle').click(); true")
    assert evaluate(page, "document.documentElement.dataset.motion") == "on"
    # Repeat real button/API theme updates without losing entered text.
    evaluate(page, "document.querySelector('#url').value='retained source'; true")
    for _ in range(10):
        before = evaluate(page, "document.documentElement.dataset.theme")
        evaluate(page, "document.querySelector('#themeBtn').click(); true")
        wait_until(lambda before=before: evaluate(page, "document.documentElement.dataset.theme") != before)
    assert evaluate(page, "document.querySelector('#url').value") == "retained source"
    evaluate(page, "document.querySelector('#url').focus(); true")
    proxy = view.focusProxy() or view
    before_keyboard = evaluate(page, "document.documentElement.dataset.theme")
    QTest.keyClick(proxy, Qt.Key_T, Qt.ControlModifier)
    QTest.qWait(200)
    after_keyboard = evaluate(page, "document.documentElement.dataset.theme")
    assert before_keyboard != after_keyboard, "Ctrl T must toggle the real browser theme"
    assert not page.errors, page.errors
    result = {"renders": checks, "javascript_errors": page.errors,
              "theme_toggles": 10, "empty_source_validation": True,
              "input_retained": True, "crt_toggle": True, "keyboard_theme_shortcut": True}
    (out / "web-render-report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    view.close()
    view.setPage(QWebEnginePage(view))
    page.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
