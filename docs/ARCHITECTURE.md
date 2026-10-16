# Architecture notes

Why the code is shaped the way it is. Short version of the decisions that
aren't obvious from reading it.

---

## 1. The progress-feed bug that shaped the engine

The original design shelled out to yt-dlp and parsed its stdout:

```
[download]  42.1% of ~ 10.20MiB at  3.20MiB/s ETA 00:02
```

This **cannot work**. yt-dlp only renders those lines when stdout is a TTY.
Under `subprocess.PIPE` it writes nothing at all. The symptom is deceptive —
files download correctly, the UI reports 0%, and nothing looks broken.

Verified directly:

```bash
python -m yt_dlp --newline ... 1>/dev/null   # zero [download] lines
python -m yt_dlp --newline ... 2>&1          # only WARNINGs
```

The fix is the Python API:

```python
ydl = YoutubeDL({"progress_hooks": [hook]})
# hook receives {"status","downloaded_bytes","total_bytes","speed","eta"}
```

Structured data, no parsing, no TTY requirement.

**Lesson kept in code:** `engine/downloader.py` documents this at the top so
nobody "simplifies" it back to a subprocess.

---

## 2. Throttling

`progress_hooks` fires per network chunk. At 3 MB/s with 32 KB chunks that is
~90 callbacks/sec. Forwarded raw into a Qt signal, the event loop saturates and
the window stops painting — the UI looks frozen while the download races ahead.

`_ProgressThrottle` coalesces to ~12/sec and keeps the last suppressed payload
so `flush()` can emit the true final value. Discrete state changes
(`extracting`, `processing`, `tagging`, `done`) bypass the throttle with
`force()`.

---

## 3. stderr must be drained

The subprocess version read stdout and left `stderr=subprocess.PIPE` undrained.
Once the child filled the ~64 KB OS buffer it blocked on write, and the parent
blocked on read: a total freeze with no error message.

The API version removes the problem entirely (no subprocess), but the rule
stands: *never create a PIPE you do not read.*

---

## 4. Quality presets actually change the file

The original `_QUALITY_FORMATS` only set `--format bestaudio[abr<=320]`. Without
`-x --audio-format`, yt-dlp keeps the raw stream — so every "320 kbps" download
was a `.webm` opus file and the quality selector did nothing.

Now each `Quality` owns three things:

- `format_selector` — which source stream to grab
- `audio_format` — target container, or `None` to keep the source codec
- `postprocessor_args` — encoder settings

`BEST.audio_format is None` on purpose: forcing mp3 there would discard the
bitrate the selector just chose.

---

## 5. FastAPI + `from __future__ import annotations`

The request models were originally defined *inside* `create_app()`. With
`from __future__ import annotations`, FastAPI sees the annotation as the string
`"DownloadRequest"` and resolves it against **module globals**. The local class
isn't there, so FastAPI silently degraded the request body into query
parameters and every POST returned `422 Field required: query.req`.

The models now live at module scope with a comment explaining why they must
stay there. This is a genuinely nasty failure mode — no traceback, no warning,
just a 422.

---

## 6. SoundCloud playlists

`_is_single_url()` originally matched the bare substring `"soundcloud.com/"`,
which matches every SoundCloud URL — including `/artist/sets/playlist`. Every
playlist was therefore treated as a single track and `--no-playlist` was passed.

Now playlist shapes (`/sets/`, `/playlist`, `?list=`) are tested *first* and
return False before any per-host matching. Caught by
`test_playlist_urls` in `tests/test_engine.py`.

---

## 7. Theme as data, not as strings

Colours live in a frozen `Palette` dataclass. `theme.py` generates the entire
QSS from it, and `web/assets.py` injects the same tokens into CSS custom
properties. One palette object feeds a Qt stylesheet *and* a stylesheet-free
HTML page, so the two UIs cannot drift.

The light palette is hand-tuned, not an inversion of the dark one. A test
asserts the two differ in every visible token, and another asserts every token
is a valid hex string — a typo'd or inverted palette fails the suite.

---

## 8. Settings that survive bad input

`Settings` is a small JSON store with:

- **atomic writes** — `mkstemp` + `os.replace`, so a crash mid-save cannot
  corrupt the file
- **key allowlist** — unknown keys in a hand-edited file are dropped
- **clamping** — `parallel: 9999` becomes 8, `quality: "nope"` becomes `"high"`
- **corruption tolerance** — invalid JSON falls back to defaults, never raises

Preferences are not worth an unhandled exception at startup.

---

## Things deliberately not done

- **No Spotify API / client credentials.** The public oEmbed endpoint gives
  title, artist and artwork with no auth. Whole playlists work because yt-dlp
  ships a metadata-only Spotify extractor.
- **No Qt web engine.** The browser dashboard is FastAPI + vanilla JS; the
  desktop app is native PySide6. No Electron anywhere.
- **No playlist database.** Queue state is in memory. Restarting clears it,
  which is the correct behaviour for a downloader.
- **No `--no-progress` in the yt-dlp invocation.** That flag kills the progress
  feed. The comment in `_build_command` exists to stop it coming back.