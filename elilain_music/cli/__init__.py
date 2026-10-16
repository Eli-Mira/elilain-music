"""CLI — `python -m elilain_music.cli <command>`.

Commands:
    down <url|search>   download one track, playlist, or Spotify link
    info <url>          show what a link resolves to, download nothing
    gui                 launch the desktop app
    web [--port N]      launch the browser dashboard
    doctor              check ffmpeg / yt-dlp / settings
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ..engine import Downloader, DownloadJob, EngineConfig, Quality, Track
from ..gui.settings import Settings

log = logging.getLogger("elilain.cli")

SPOTIFY_MARKERS = ("spotify:", "spotify.com", "open.spotify.com")


def human_bytes(n: float) -> str:
    if not n:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def human_eta(s: float) -> str:
    if not s or s < 0:
        return "—"
    s = int(s)
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    return f"{m}m {sec:02d}s" if m < 60 else f"{m // 60}h {m % 60:02d}m"


def is_spotify(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in SPOTIFY_MARKERS)


def resolve_input(raw: str, search: bool, quiet: bool = False) -> Track:
    """Turn user input into a Track with a downloadable webpage_url."""
    if is_spotify(raw):
        from ..engine.spotify import SpotifyMetadataResolver

        if not quiet:
            print("Resolving Spotify link…")
        try:
            res = SpotifyMetadataResolver(deep_search=True).resolve(raw)
        except Exception as exc:  # noqa: BLE001
            print(f"Spotify resolve failed: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        if not res.matched_track:
            print(f"No free source found for: {res.display}", file=sys.stderr)
            raise SystemExit(1)
        if not quiet:
            print(f"  {res.display}  ->  {res.matched_track.source.value}")
        return res.matched_track

    if search or not raw.lower().startswith(("http://", "https://")):
        from ..engine.spotify import SpotifyMetadataResolver

        query = raw if search else raw
        if not quiet:
            print(f"Searching for: {query}")
        tracks = SpotifyMetadataResolver().search(query, "ytsearch1")
        if not tracks:
            print("No results.", file=sys.stderr)
            raise SystemExit(1)
        if not quiet:
            print(f"  {tracks[0].title}")
        return tracks[0]

    return Track(id="", title=raw, webpage_url=raw)


def cmd_down(a: argparse.Namespace) -> int:
    settings = Settings()
    output_dir = a.out or settings.get("output_dir")
    quality = Quality(a.quality)

    track = resolve_input(a.url, a.search)
    job = DownloadJob(
        track=track,
        quality=quality,
        output_dir=output_dir,
        overwrite=a.overwrite,
        embed_metadata=not a.no_tags,
        embed_thumbnail=not a.no_cover,
    )

    dl = Downloader(EngineConfig(
        max_parallel_downloads=a.jobs,
        max_network_split=a.fragments,
        output_dir=output_dir,
        proxy=a.proxy or "",
    ))

    print(f"Quality : {quality.label}")
    print(f"Output  : {output_dir}")
    print("-" * 60)

    last_line_len = 0

    def on_progress(status: str, pct: float, bps: float, eta: float) -> None:
        nonlocal last_line_len
        bar_w = 28
        filled = int(bar_w * pct / 100)
        bar = "█" * filled + "·" * (bar_w - filled)
        line = f"  [{bar}] {pct:5.1f}%  {human_bytes(bps):>9}/s  ETA {human_eta(eta):>7}  {status}"
        pad = max(0, last_line_len - len(line))
        sys.stdout.write("\r" + line + " " * pad)
        sys.stdout.flush()
        last_line_len = len(line)

    try:
        result = dl.download(job, on_progress=on_progress)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        dl.cancel_all()
        return 130

    sys.stdout.write("\r" + " " * (last_line_len + 2) + "\r")

    if not result.success:
        print(f"FAILED  {result.error}", file=sys.stderr)
        return 1

    n = len(result.files) or 1
    print(f"OK      {human_eta(result.elapsed_seconds)}")
    for f in result.files:
        print(f"        {f}")
    if n > 1:
        print(f"        ({n} files)")
    return 0


def cmd_info(a: argparse.Namespace) -> int:
    track = resolve_input(a.url, a.search)
    print(f"title    : {track.title}")
    print(f"artist   : {track.artist or '—'}")
    print(f"source   : {track.source.value}")
    print(f"duration : {track.duration_label}")
    print(f"url      : {track.webpage_url}")
    if track.tags:
        print(f"tags     : {', '.join(track.tags)}")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    from ..engine.engine_config import discover_ffmpeg

    settings = Settings()
    ff = discover_ffmpeg()

    print("EliLain-Music — environment check")
    print("-" * 40)
    print(f"python           : {sys.version.split()[0]}")
    print(f"yt-dlp           : {Downloader.version()}")
    print(f"ffmpeg           : {ff or 'NOT FOUND  <- audio conversion will fail'}")
    print(f"config file      : {settings.path}")
    print(f"saved theme      : {settings.get('theme')}")
    print(f"default quality  : {settings.get('quality')}")
    print(f"output directory : {settings.get('output_dir')}")
    print(f"destination ok   : {Path(settings.get('output_dir')).is_dir() or 'will be created'}")

    try:
        import PySide6  # noqa: F401
        print(f"PySide6          : {PySide6.__version__}  (desktop GUI available)")
    except ImportError:
        print("PySide6          : not installed  (GUI unavailable)")
    try:
        import fastapi  # noqa: F401
        print(f"FastAPI          : {fastapi.__version__}  (web dashboard available)")
    except ImportError:
        print("FastAPI          : not installed  (web unavailable)")

    print("-" * 40)
    ok = bool(ff)
    print("READY" if ok else "NOT READY — install ffmpeg first")
    return 0 if ok else 1


def cmd_gui(_: argparse.Namespace) -> int:
    from ..gui.qml import main as gui_main

    return gui_main()


def cmd_web(a: argparse.Namespace) -> int:
    from ..web.main import main as web_main

    argv = ["--port", str(a.port)] if a.port else []
    return web_main(argv)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="elilain-music",
        description="EliLain-Music — local, free, high-speed music downloader.",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("down", help="download a link or search query")
    d.add_argument("url", help="YouTube / YT Music / SoundCloud / Spotify link, or a search")
    d.add_argument("-q", "--quality", default=None,
                   choices=[q.value for q in Quality], help="audio quality (default: high)")
    d.add_argument("-o", "--out", default="", help="output directory")
    d.add_argument("-j", "--jobs", type=int, default=1, help="parallel tracks (playlists)")
    d.add_argument("-f", "--fragments", type=int, default=8, help="network fragments per track")
    d.add_argument("--search", action="store_true", help="force search-query mode")
    d.add_argument("--overwrite", action="store_true", help="replace existing files")
    d.add_argument("--no-tags", action="store_true", help="skip metadata embedding")
    d.add_argument("--no-cover", action="store_true", help="skip thumbnail embedding")
    d.add_argument("--proxy", default="", help="proxy URL")
    d.set_defaults(func=cmd_down)

    i = sub.add_parser("info", help="resolve a link and print details")
    i.add_argument("url")
    i.add_argument("--search", action="store_true")
    i.set_defaults(func=cmd_info)

    g = sub.add_parser("gui", help="launch the desktop app")
    g.set_defaults(func=cmd_gui)

    w = sub.add_parser("web", help="launch the browser dashboard")
    w.add_argument("--port", type=int, default=0)
    w.set_defaults(func=cmd_web)

    doc = sub.add_parser("doctor", help="check the environment")
    doc.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    a = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if not getattr(a, "cmd", None):
        parser.print_help()
        return 0

    # 'down' inherits quality from settings when not given explicitly
    if a.cmd == "down" and a.quality is None:
        a.quality = Settings().get("quality")

    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
