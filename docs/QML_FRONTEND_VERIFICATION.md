# QML frontend verification — October 3, 2026

## Delivered

Native PySide6 / Qt Quick frontend: `elilain_music/gui/qml.py`,
`elilain_music/gui/quick/Main.qml`, `SignalButton.qml`, and `SignalToggle.qml`.
Module, CLI GUI command and installed GUI-script entry points select QML.
The existing desktop launchers invoke that module and therefore pick up QML.
The QWidget frontend remains as legacy code with its regression coverage.

The supplied Lain portrait, secondary scene and reaching-hands banner are
bundled locally. Native and browser interfaces use the same typed dark/light
palette. Custom keycaps, control states, optional CRT motion and real empty,
error and transfer states are implemented.

## Executed checks

- Offline suite: **109 passed, 3 opt-in network tests skipped**.
- One upstream Starlette/AnyIO deprecation warning; no test failure.
- `ruff check .`: **All checks passed**.
- QML renderer: dark/light at 1340×940 and 1120×820; actual background-pixel
  assertions; zero out-of-window controls; zero QML diagnostics.
- Sidebar regression checks both window sizes with the production Segoe UI
  font and asserts content stays inside the card's bottom padding.
- Ten QML theme switches preserve input and the same root window.
- Real Qt mouse/key tests verify source focus/selection, theme shortcuts,
  format selection, fragments, optional motion, persisted preferences and
  empty-source validation.
- Actual QThread fixture tests verify error/empty results, responsive deferred
  close, worker retention until finished, cancellation and safe queue clearing.
  Injected fixture results are not presented as live source-service downloads.
- Real HTTP dashboard rendered in isolated Chromium (QtWebEngine): dark/light
  at 1340px, 390px and 320px; all three images loaded, no horizontal overflow,
  no JavaScript console errors. Ten theme changes preserve input; empty-source
  validation, CRT toggle and Ctrl T exercised. The offscreen Chromium backend
  logged GPU-context fallback warnings, but rendering and assertions completed.
- Wheel built successfully and inspected: all three QML files and five
  artwork/credit files are present. Installed GUI entry point is
  `elilain_music.gui.qml:main`.
- CLI doctor returns **READY**. Live native desktop window observed and
  captured by exact process/window ID with accessible controls and local art.
  Screenshot: `docs/previews/qml-desktop-live.png`.
- Temporary QA web server stopped after verification. The native app was
  launched and captured; the final process check subsequently observed a clean
  exit (code 0), so it is not being claimed to remain open.

## Scope and unresolved findings

This completes the requested frontend migration/design work, **not a fresh
source-service or full download-engine certification**. Earlier audit findings
about job-scoped output attribution, playlist result accounting and advertised
quality/cover behavior are not repaired by this frontend change. The new QML
bridge rejects success with no nonempty file, but that alone does not establish
file provenance. See the earlier engine audit and Obsidian session history.

Artwork copyrights/redistribution permissions are unverified and separate
from the Prosperity code license. No deployment or publication was performed.
