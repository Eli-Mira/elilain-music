"""Engine configuration — single source of truth."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Hermes ships a static ffmpeg build; look there when the system PATH has none.
_CANDIDATE_FFMPEG_ROOTS = [
    os.path.expandvars(r"%LOCALAPPDATA%\hermes\tools"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\hermes\tools"),
]


def discover_ffmpeg() -> str:
    """Return a usable ffmpeg path, or '' if none found.

    yt-dlp needs ffmpeg (on PATH or via --ffmpeg-location) for audio extraction,
    metadata embedding and thumbnail muxing. Without it the download "succeeds"
    but you get a raw .webm with no tags — so hunt for one before giving up.
    """
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    for root in _CANDIDATE_FFMPEG_ROOTS:
        base = Path(root)
        if not base.is_dir():
            continue
        for pattern in ("ffmpeg-*/bin/ffmpeg.exe", "ffmpeg-*/bin/ffmpeg"):
            for candidate in sorted(base.glob(pattern), reverse=True):
                if candidate.is_file():
                    return str(candidate)
    return ""


def ffmpeg_available() -> bool:
    return bool(discover_ffmpeg())


@dataclass
class EngineConfig:
    """Runtime knobs for the download engine."""

    max_parallel_downloads: int = 4        # tracks in flight at once
    max_network_split: int = 8             # fragments per track (speed)
    output_dir: str = ""
    cookie_file: str = ""
    proxy: str = ""
    ffmpeg_bin: str = field(default_factory=discover_ffmpeg)

    # Robustness
    retries: int = 8
    fragment_retries: int = 8
    socket_timeout: int = 30

    def resolved_output_dir(self) -> Path:
        d = self.output_dir or str(Path.home() / "Music" / "EliLain")
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        return p
