"""Spotify resolution.

Spotify's own audio is not downloadable — that is the business model, not a bug.
What we do instead is free and legal:

  1. pull the track's real title/artist from Spotify's public oEmbed endpoint
     (no auth, no API key, no account),
  2. find the same recording on YouTube / YouTube Music / SoundCloud via
     yt-dlp's search extractors,
  3. download from there.

Whole Spotify playlists work too: yt-dlp ships a metadata-only Spotify
extractor, so we pull the track IDs then resolve each one.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from .models import Source, Track

log = logging.getLogger("elilain.spotify")

OEMBED_URL = "https://open.spotify.com/oembed"
USER_AGENT = "EliLain-Music/0.1 (+local)"

_TRACK_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")


@dataclass
class SpotifyResolved:
    spotify_id: str
    title: str
    artist: str
    kind: str = "track"
    matched_track: Track | None = None
    candidates: list[Track] = field(default_factory=list)

    @property
    def display(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title


def _yt_dlp_cmd() -> list[str]:
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        exe = shutil.which("yt-dlp")
        if exe:
            return [exe]
    raise RuntimeError("yt-dlp not found. Run: pip install yt-dlp")


def parse_spotify_ref(url_or_id: str) -> tuple[str, str]:
    """Return (id, kind) from a spotify URI, a web URL, or a bare 22-char ID.

    Accepts:
        spotify:track:ID
        https://open.spotify.com/track/ID
        https://open.spotify.com/intl-de/track/ID
        https://open.spotify.com/embed/track/ID
        ID
    """
    s = (url_or_id or "").strip()
    if not s:
        raise ValueError("empty Spotify reference")

    if s.lower().startswith("spotify:"):
        parts = s[8:].split(":")
        if len(parts) >= 2 and parts[0] in ("track", "album", "playlist", "episode"):
            return parts[1], parts[0]
        raise ValueError(f"unsupported Spotify URI: {url_or_id}")

    if "spotify.com" in s.lower():
        seg = [p for p in urlparse(s).path.split("/") if p]
        # drop locale prefixes like 'intl-de'
        seg = [p for p in seg if not p.startswith("intl-")]
        if "embed" in seg:
            seg = [p for p in seg if p != "embed"]
        if len(seg) >= 2 and seg[0] in ("track", "album", "playlist", "episode"):
            return seg[1], seg[0]
        raise ValueError(f"could not find a track id in Spotify URL: {url_or_id}")

    if _TRACK_ID_RE.match(s):
        return s, "track"

    raise ValueError(f"not a Spotify link or id: {url_or_id}")


def fetch_metadata(track_id: str, timeout: int = 15) -> dict:
    """Title/artist/thumbnail from Spotify's public oEmbed. No auth required."""
    resp = requests.get(
        f"{OEMBED_URL}?url=https://open.spotify.com/track/{track_id}",
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    raw_title = (data.get("title") or "").strip()
    artist, sep, rest = raw_title.partition(" - ")
    if sep and rest.strip():
        return {
            "title": rest.strip(),
            "artist": artist.strip(),
            "thumbnail": data.get("thumbnail_url", ""),
            "raw_title": raw_title,
        }
    return {"title": raw_title, "artist": "", "thumbnail": data.get("thumbnail_url", ""), "raw_title": raw_title}


class SpotifyMetadataResolver:
    """Turns a Spotify reference into a downloadable Track from another source."""

    # Search keys, tried in order. YouTube Music is just YouTube with a music
    # bias, so it is the same extractor; SoundCloud is the fallback.
    SEARCH_KEYS = ("ytsearch1", "scsearch1")
    SEARCH_KEYS_DEEP = ("ytsearch5", "scsearch5")

    def __init__(self, timeout: int = 60, deep_search: bool = False) -> None:
        self.timeout = timeout
        self.keys = self.SEARCH_KEYS_DEEP if deep_search else self.SEARCH_KEYS
        self._cmd = _yt_dlp_cmd()

    # ------------------------------------------------------------------ #
    def resolve(self, url: str) -> SpotifyResolved:
        track_id, kind = parse_spotify_ref(url)
        if kind != "track":
            raise ValueError(
                f"Only single Spotify tracks resolve directly (got kind={kind!r}). "
                f"Use resolve_playlist() for album/playlist links."
            )

        meta = fetch_metadata(track_id)
        query = f"{meta['artist']} {meta['title']}".strip()

        candidates: list[Track] = []
        for key in self.keys:
            candidates = self.search(query, key)
            if candidates:
                break

        matched: Track | None = None
        if candidates:
            best = candidates[0]
            # Keep the authoritative Spotify name even if the match's own
            # title field is messy ("Artist - Title (Official Video)").
            best.artist = best.artist or meta["artist"]
            best.title = meta["title"] or best.title
            best.thumbnail = best.thumbnail or meta.get("thumbnail", "")
            best.tags.append("spotify")
            best.tags.append(f"spotify:{track_id}")
            matched = best

        return SpotifyResolved(
            spotify_id=track_id,
            title=meta["title"],
            artist=meta["artist"],
            kind="track",
            matched_track=matched,
            candidates=candidates,
        )

    def resolve_playlist(self, url: str, limit: int = 500) -> list[SpotifyResolved]:
        """Resolve every track in a Spotify album/playlist."""
        _, kind = parse_spotify_ref(url)
        if kind == "track":
            return [self.resolve(url)]

        ids = self._extract_ids(url, limit)
        out: list[SpotifyResolved] = []
        for i, tid in enumerate(ids):
            if self._stop_requested():
                break
            try:
                out.append(self.resolve(f"spotify:track:{tid}"))
            except Exception as exc:  # noqa: BLE001
                log.warning("playlist track %d (%s) failed: %s", i, tid, exc)
            time.sleep(0.25)   # be gentle with search
        return out

    _stop = False

    def _stop_requested(self) -> bool:
        return self._stop

    def stop(self) -> None:
        self._stop = True

    def _extract_ids(self, url: str, limit: int) -> list[str]:
        cmd = [
            *self._cmd,
            "--flat-playlist",
            "--ignore-config",
            "--print", "url",
            "--playlist-end", str(limit),
            url,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=300, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            log.warning("spotify playlist extraction timed out")
            return []
        if proc.returncode != 0:
            raise RuntimeError(
                f"yt-dlp could not read that Spotify {url!r} "
                f"({proc.stderr.strip()[-300:] or 'unknown error'}). "
                f"Spotify may have changed its page structure — update yt-dlp."
            )

        ids: list[str] = []
        seen: set[str] = set()
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            m = (
                re.search(r"spotify:track:([A-Za-z0-9]{22})", line)
                or re.search(r"open\.spotify\.com/(?:embed/)?(?:intl-[a-z]+/)?track/([A-Za-z0-9]{22})", line)
            )
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                ids.append(m.group(1))
        return ids

    # ------------------------------------------------------------------ #
    def search(self, query: str, search_key: str = "ytsearch1") -> list[Track]:
        """Run a yt-dlp search and return candidate tracks (nothing is downloaded)."""
        if not query.strip():
            return []
        template = json.dumps(
            {
                "id": "%(id)s",
                "title": "%(title)s",
                "artist": "%(artist,channel,uploader,creator)s",
                "duration": "%(duration)s",
                "thumbnail": "%(thumbnail)s",
                "url": "%(webpage_url)s",
                "ext": "%(ext)s",
                "view_count": "%(view_count)s",
            },
            separators=(",", ":"),
        )
        cmd = [
            *self._cmd,
            "--ignore-config",
            "--no-download",
            "--flat-playlist",
            "--print", template,
            "--no-warnings",
            f"{search_key}:{query}",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=self.timeout, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            log.warning("search timed out for %r", query)
            return []
        if proc.returncode != 0:
            log.warning("search failed for %r: %s", query, proc.stderr.strip()[-300:])
            return []

        tracks: list[Track] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = d.get("url") or ""
            if not url:
                continue
            src = Source.SOUNDCLOUD if "soundcloud" in url else Source.YOUTUBE
            tracks.append(
                Track(
                    id=str(d.get("id") or ""),
                    title=str(d.get("title") or query),
                    artist=str(d.get("artist") or ""),
                    duration=_as_int(d.get("duration")),
                    thumbnail=str(d.get("thumbnail") or ""),
                    webpage_url=url,
                    source=src,
                    ext=str(d.get("ext") or ""),
                )
            )
        return tracks


def _as_int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None
