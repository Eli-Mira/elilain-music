# EliLain-Music

**Local. Free. Yours.**

A music downloader with a native **PySide6 + QML / Qt Quick** Lain-themed desktop
app and a matching browser dashboard. Pulls
audio from YouTube, YouTube Music and SoundCloud, and resolves Spotify links to
a free source. No account, no API key, no cloud service, no paywall.

---

## Quick start

```bash
cd C:/Projects/CODING/CODINGWITHMIRA/elilain-music
python -m pip install -e ".[dev]"

python -m elilain_music.cli doctor     # check the environment
python -m elilain_music.gui            # desktop app
```

Or double-click `launch-gui.bat` / `launch-web.bat`.

---

## The three ways in

### Desktop app

```bash
python -m elilain_music.gui
```

Paste a link or type a search, pick a quality, hit Download. Live speed and ETA,
per-item status, working Stop button, dark/light theme that persists.

The desktop frontend is Qt Quick, not an embedded browser or a recoloured
QWidget window. Custom buttons, keycaps, toggles and format controls share a
typed palette with the browser. Your supplied portrait, scene and banner are
bundled locally; there are no hotlinked artwork or web-font dependencies.
Downloads still require an internet connection.

**Shortcuts:** `Ctrl L` focuses/selects the source, `Enter` or `Ctrl Enter`
starts a transfer, `Ctrl T` switches themes, and `Esc` stops the active transfer.
CRT motion is optional and off by default.

Closing during a transfer requests cancellation and waits asynchronously for
the worker thread to finish; it does not destroy a running QThread or freeze
the interface. A queue row is only marked Saved after a nonempty output file
has been verified.

### Browser dashboard

```bash
python -m elilain_music.web            # http://127.0.0.1:8081
python -m elilain_music.web --port 9000
```

Same engine, same theme tokens as the desktop app. Binds to `127.0.0.1` only.

### CLI

```bash
# by link
python -m elilain_music.cli down "https://youtube.com/watch?v=..."

# by search
python -m elilain_music.cli down "billie eilish bad guy" --search

# Spotify (resolved to a free source)
python -m elilain_music.cli down "https://open.spotify.com/track/..."

# what does this link resolve to? downloads nothing
python -m elilain_music.cli info "spotify:track:4cOdK2wGLETKBW3PvgPWqT"

# quality + parallelism + destination
python -m elilain_music.cli down "<url>" -q lossless -j 4 -o "D:/Music"

# is everything installed?
python -m elilain_music.cli doctor
```

---

## Quality presets

| Preset | Container | Notes |
|---|---|---|
| `low` | opus | ~96 kbps, smallest files |
| `medium` | opus | ~192 kbps |
| `high` | **mp3** | ~320 kbps, re-encoded — maximum compatibility |
| `best` | *source codec* | highest available bitrate, **no re-encode** |
| `lossless` | flac | when the source has it |

`best` deliberately does not force mp3. Converting to mp3 would throw away the
very bitrate the format selector just chose, so it hands you the original
stream instead.

---

## Architecture

```
elilain_music/
├── engine/
│   ├── models.py         Track, Playlist, Quality, Source, DownloadJob/Result
│   ├── engine_config.py  EngineConfig + ffmpeg discovery
│   ├── downloader.py     yt-dlp Python API wrapper, thread pool, cancellation
│   └── spotify.py        Spotify ref parsing + oEmbed metadata + source matching
├── gui/
│   ├── theme.py          Palette dataclass, DARK/LIGHT, QSS generator
│   ├── settings.py       atomic JSON persistence
│   ├── qml.py            QObject bridge, data-only queue, retained QThread worker
│   ├── quick/*.qml       Qt Quick window and reusable native controls
│   └── window.py         legacy QWidget implementation, retained for regression tests
├── web/
│   ├── main.py           FastAPI app, job store, REST endpoints
│   └── assets.py         dashboard HTML, palette injected from theme.py
├── cli/
│   └── __init__.py       argparse CLI: down / info / gui / web / doctor
└── tests/                engine, API, legacy GUI and QML acceptance tests
```

### Why the yt-dlp Python API and not the CLI

The first version shelled out to `yt-dlp` and scraped its stdout for
`[download] 42.1% of … at 3.2MiB/s ETA 00:02`. **That never works.** yt-dlp only
writes human-readable progress when stdout is a TTY; under `subprocess.PIPE` it
emits nothing. The progress bar sat at 0% forever while files downloaded
correctly in the background.

`engine/downloader.py` now uses `YoutubeDL(progress_hooks=…)`, which delivers
structured `downloaded_bytes / total_bytes / speed / eta`. Hooks fire per network
chunk (~90/sec at 3 MB/s), so they are coalesced by `_ProgressThrottle` to
~12/sec before reaching a Qt signal — otherwise the event loop saturates and the
window stops repainting.

### Cancellation

`Downloader.cancel_all()` sets a flag that the progress hook observes and raises
from, aborting yt-dlp cleanly. Verified by `test_live_cancel_stops_the_job`.

---

## Requirements

- Python 3.10+
- **ffmpeg** — required for audio conversion, tag embedding and cover art.
  `doctor` finds it on PATH or in the Hermes tools directory:
  `%LOCALAPPDATA%\hermes\tools\ffmpeg-*/bin/ffmpeg.exe`
- `yt-dlp`, `PySide6`, `fastapi`, `uvicorn`, `requests`, `pydantic` — all via pip

Without ffmpeg the app still runs, but you get the raw stream with no tags.

---

## Settings

Stored at `%LOCALAPPDATA%\EliLain-Music\settings.json`:

```json
{
  "theme": "dark",
  "quality": "high",
  "parallel": 4,
  "fragments": 8,
  "output_dir": "C:\\Users\\you\\Music\\EliLain",
  "embed_metadata": true,
  "embed_thumbnail": true,
  "overwrite": false
}
```

Writes are atomic, unknown keys are rejected, out-of-range numbers are clamped,
and a corrupt file falls back to defaults instead of crashing.

---

## Tests

```bash
python -m pytest                      # offline regression suite
ELM_LIVE=1 python -m pytest          # opt-in source-service integration tests
python -m ruff check .
python tools/render_qml.py out/qml/  # real QML pixels, both modes and window sizes
python tools/render_check.py out/    # legacy QWidget regression renderer
python tools/serve_uiqa.py            # isolated loopback browser QA server
python tools/render_web.py "%LOCALAPPDATA%/hermes/cache/scratch/elilain-browser-preview"
```

`tools/render_qml.py` instantiates the real QML engine, renders dark and light
modes at 1340×940 and 1120×820, samples actual background pixels, checks control
bounds, repeats theme switching, and fails on QML diagnostics.

`tools/render_web.py` uses the Chromium engine bundled with PySide6 QtWebEngine
to render the real HTTP dashboard at desktop, 390px and 320px widths. It checks
image loading, horizontal reflow, validation, persisted theme switching and the
keyboard shortcut. QA settings are isolated from the user’s settings.

The QML lifecycle tests exercise actual QThreads and Qt mouse/key events without
network access, including deferred close, cancellation and failed/empty results.

---

## Legal note

This tool downloads content that is publicly accessible. What you do with it is
your responsibility: respect copyright in your jurisdiction, and only download
material you have the right to keep. Spotify audio itself is never downloaded —
only its public metadata is read, and the audio comes from a different source.

## License

Code: MIT. User-supplied Lain artwork remains © its respective rights holders
and is **not** covered by the code license. Author credits and redistribution
permissions have not been verified; see `elilain_music/assets/CREDITS.md`.