"""Download engine — wraps yt-dlp for YouTube / YouTube Music / SoundCloud, plus Spotify metadata."""

from .downloader import Downloader, DownloadJob, DownloadResult
from .engine_config import EngineConfig
from .models import Playlist, Quality, Source, Track
from .spotify import SpotifyMetadataResolver

__all__ = [
    "Downloader",
    "DownloadJob",
    "DownloadResult",
    "EngineConfig",
    "SpotifyMetadataResolver",
    "Track",
    "Playlist",
    "Quality",
    "Source",
]
