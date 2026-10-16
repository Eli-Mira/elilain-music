"""Domain models — Track, Playlist, Quality, Source."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Source(str, Enum):
    YOUTUBE = "youtube"
    YOUTUBE_MUSIC = "youtube_music"
    SOUNDCLOUD = "soundcloud"
    SPOTIFY = "spotify"


class Quality(str, Enum):
    """Audio quality presets mapped to yt-dlp format selectors + post-processing."""

    LOW = "low"            # ~96 kbps opus/m4a
    MEDIUM = "medium"      # ~192 kbps
    HIGH = "high"          # ~320 kbps mp3
    BEST = "best"          # highest source bitrate, kept in native codec
    LOSSLESS = "lossless"  # flac when the source has it

    @property
    def format_selector(self) -> str:
        return _QUALITY_FORMATS[self]

    @property
    def audio_format(self) -> str | None:
        """Target container passed to yt-dlp's -x --audio-format.

        None means "keep the source codec" — correct for BEST, because forcing
        mp3 there would throw away the very bitrate we just selected.
        """
        return _QUALITY_CONTAINERS.get(self)

    @property
    def label(self) -> str:
        return _QUALITY_LABELS[self]

    @property
    def postprocessor_args(self) -> list[str]:
        """Extra args applied after extraction (e.g. mp3 bitrate)."""
        if self is Quality.HIGH:
            return ["--audio-quality", "0"]
        return []


@dataclass
class Track:
    id: str
    title: str
    artist: str = ""
    album: str = ""
    duration: int | None = None       # seconds
    thumbnail: str = ""
    webpage_url: str = ""
    source: Source = Source.YOUTUBE
    extractor_key: str = ""
    ext: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title

    @property
    def duration_label(self) -> str:
        if not self.duration:
            return "--:--"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@dataclass
class Playlist:
    id: str
    title: str
    source: Source
    tracks: list[Track] = field(default_factory=list)
    thumbnail: str = ""
    webpage_url: str = ""

    @property
    def display(self) -> str:
        return f"{self.title} ({len(self.tracks)} tracks)"


@dataclass
class DownloadJob:
    track: Track
    quality: Quality = Quality.HIGH
    output_dir: str = ""
    filename_template: str = "%(artist)s - %(title)s.%(ext)s"
    overwrite: bool = False
    embed_metadata: bool = True
    embed_thumbnail: bool = True

    @property
    def format_selector(self) -> str:
        """yt-dlp format string for the requested quality."""
        return self.quality.format_selector


@dataclass
class DownloadResult:
    job: DownloadJob
    success: bool
    path: str = ""
    error: str = ""
    elapsed_seconds: float = 0.0
    files: list[str] = field(default_factory=list)   # playlist -> many files


_QUALITY_FORMATS: dict[Quality, str] = {
    Quality.LOW: "bestaudio[abr<=96]/bestaudio",
    Quality.MEDIUM: "bestaudio[abr<=192]/bestaudio",
    Quality.HIGH: "bestaudio[abr<=320]/bestaudio",
    Quality.BEST: "bestaudio/best",
    Quality.LOSSLESS: "bestaudio[ext=flac]/bestaudio[acodec=flac]/bestaudio/best",
}

# None == leave the downloaded stream untouched (no re-encode).
_QUALITY_CONTAINERS: dict[Quality, str | None] = {
    Quality.LOW: "opus",
    Quality.MEDIUM: "opus",
    Quality.HIGH: "mp3",
    Quality.BEST: None,
    Quality.LOSSLESS: "flac",
}

_QUALITY_LABELS: dict[Quality, str] = {
    Quality.LOW: "Low · 96 kbps opus",
    Quality.MEDIUM: "Medium · 192 kbps opus",
    Quality.HIGH: "High · 320 kbps mp3",
    Quality.BEST: "Best · native codec",
    Quality.LOSSLESS: "Lossless · FLAC",
}
