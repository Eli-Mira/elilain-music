"""Tests for the engine — offline units plus opt-in live smoke tests.

Live tests are skipped unless ELM_LIVE=1, so the default run stays fast and
network-free:

    python -m pytest -q              # offline
    ELM_LIVE=1 python -m pytest -q    # includes real downloads
"""

from __future__ import annotations

import os

import pytest

from elilain_music.engine import (
    Downloader,
    DownloadJob,
    EngineConfig,
    Quality,
    Source,
    Track,
)
from elilain_music.engine.engine_config import discover_ffmpeg
from elilain_music.engine.models import _QUALITY_CONTAINERS, _QUALITY_FORMATS

LIVE = os.environ.get("ELM_LIVE") == "1"
needs_live = pytest.mark.skipif(not LIVE, reason="set ELM_LIVE=1 to run network tests")

# Short Creative-Commons clip, stable for years.
LIVE_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"


# ==================================================================== #
# Quality
# ==================================================================== #
def test_every_quality_has_a_format_selector():
    for q in Quality:
        assert _QUALITY_FORMATS[q]
        assert isinstance(q.label, str) and q.label


def test_every_quality_has_a_container_entry():
    # None is legal (BEST keeps the native codec) but the key must exist.
    for q in Quality:
        assert q in _QUALITY_CONTAINERS


def test_lossless_requests_flac():
    assert Quality.LOSSLESS.audio_format == "flac"
    assert "flac" in Quality.LOSSLESS.format_selector


def test_best_does_not_force_a_container():
    # Forcing mp3 on BEST would discard the very bitrate we just selected.
    assert Quality.BEST.audio_format is None


def test_high_requests_mp3():
    assert Quality.HIGH.audio_format == "mp3"


def test_format_selector_follows_quality():
    track = Track(id="t", title="x", webpage_url=LIVE_URL)
    a = DownloadJob(track=track, quality=Quality.LOW)
    b = DownloadJob(track=track, quality=Quality.HIGH)
    assert a.format_selector != b.format_selector


# ==================================================================== #
# Track
# ==================================================================== #
def test_track_display_with_and_without_artist():
    assert Track(id="1", title="Song", artist="Artist").display == "Artist - Song"
    assert Track(id="1", title="Song").display == "Song"


@pytest.mark.parametrize(
    "seconds,expected",
    [(None, "--:--"), (0, "--:--"), (5, "0:05"), (65, "1:05"), (3725, "1:02:05")],
)
def test_duration_label(seconds, expected):
    assert Track(id="1", title="x", duration=seconds).duration_label == expected


def test_source_values():
    assert {s.value for s in Source} == {"youtube", "youtube_music", "soundcloud", "spotify"}


# ==================================================================== #
# URL classification
# ==================================================================== #
@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/watch?v=abc",
        "https://youtu.be/abc",
        "https://www.youtube.com/shorts/abc",
        "https://www.youtube.com/live/abc",
        "https://soundcloud.com/artist/track",
        "https://open.spotify.com/track/abc",
        "just a search string",
    ],
)
def test_single_urls(url):
    assert Downloader._is_single_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/playlist?list=abc",
        "https://soundcloud.com/artist/sets/playlist",
    ],
)
def test_playlist_urls(url):
    assert Downloader._is_single_url(url) is False


# ==================================================================== #
# Engine config
# ==================================================================== #
def test_ffmpeg_is_discovered_or_reported_absent():
    # Not asserting it exists — CI boxes lack it. Assert the lookup is honest.
    path = discover_ffmpeg()
    assert isinstance(path, str)
    if path:
        assert os.path.isfile(path)


def test_resolved_output_dir_is_created(tmp_path):
    target = tmp_path / "nested" / "music"
    cfg = EngineConfig(output_dir=str(target))
    assert cfg.resolved_output_dir().is_dir()


def test_config_defaults_are_sane():
    cfg = EngineConfig()
    assert 1 <= cfg.max_parallel_downloads <= 32
    assert cfg.max_network_split >= 1


# ==================================================================== #
# Downloader scaffolding
# ==================================================================== #
def test_version_is_reported():
    assert Downloader.version() != ""


def test_cancelled_before_start_returns_failure():
    dl = Downloader()
    dl.cancel_all()
    job = DownloadJob(track=Track(id="1", title="x", webpage_url=LIVE_URL))
    res = dl.download(job)
    assert res.success is False
    assert "ancel" in res.error
    dl.reset()


def test_empty_batch_returns_empty_list():
    assert Downloader().download_many([]) == []


def test_download_many_preserves_order():
    jobs = [
        DownloadJob(track=Track(id=str(i), title=f"t{i}", webpage_url="https://x/"),
                    quality=Quality.BEST)
        for i in range(4)
    ]
    dl = Downloader(EngineConfig(max_parallel_downloads=4))
    # Unroutable host so every job fails fast; we only assert ordering.
    for j in jobs:
        j.track.webpage_url = "https://invalid.invalid/nope"
    results = dl.download_many(jobs)
    assert len(results) == 4
    assert [r.job.track.id for r in results] == ["0", "1", "2", "3"]


def test_active_count_returns_to_zero():
    dl = Downloader()
    assert dl.active_count == 0


# ==================================================================== #
# Spotify reference parsing (offline)
# ==================================================================== #
@pytest.mark.parametrize(
    "ref",
    [
        "spotify:track:4cOdK2wGLETKBW3PvgPWqT",
        "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
        "https://open.spotify.com/intl-de/track/4cOdK2wGLETKBW3PvgPWqT",
        "https://open.spotify.com/embed/track/4cOdK2wGLETKBW3PvgPWqT",
        "4cOdK2wGLETKBW3PvgPWqT",
    ],
)
def test_spotify_ref_parsing(ref):
    from elilain_music.engine.spotify import parse_spotify_ref

    track_id, kind = parse_spotify_ref(ref)
    assert track_id == "4cOdK2wGLETKBW3PvgPWqT"
    assert kind == "track"


def test_spotify_playlist_ref():
    from elilain_music.engine.spotify import parse_spotify_ref

    _, kind = parse_spotify_ref("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
    assert kind == "playlist"


@pytest.mark.parametrize("bad", ["", "not a link", "https://example.com/track/x"])
def test_spotify_bad_refs_raise(bad):
    from elilain_music.engine.spotify import parse_spotify_ref

    with pytest.raises(ValueError):
        parse_spotify_ref(bad)


# ==================================================================== #
# Live (network) tests
# ==================================================================== #
@needs_live
def test_live_download_produces_audio_file(tmp_path):
    dl = Downloader(EngineConfig(output_dir=str(tmp_path), max_network_split=4))
    job = DownloadJob(
        track=Track(id="live", title="live", webpage_url=LIVE_URL),
        quality=Quality.MEDIUM,
        output_dir=str(tmp_path),
    )
    seen: list[tuple] = []
    res = dl.download(job, on_progress=lambda *a: seen.append(a))

    assert res.success, res.error
    assert res.path and os.path.isfile(res.path)
    assert res.path.lower().endswith((".opus", ".webm", ".m4a", ".mp3"))
    assert res.elapsed_seconds > 0
    # Live progress must actually fire — this is the regression that motivated
    # moving off subprocess output scraping.
    assert any(s[0] == "downloading" for s in seen), seen[:5]
    assert any(pct > 0 for _, pct, _, _ in seen)


@needs_live
def test_live_high_quality_yields_mp3(tmp_path):
    dl = Downloader(EngineConfig(output_dir=str(tmp_path)))
    job = DownloadJob(
        track=Track(id="live", title="live", webpage_url=LIVE_URL),
        quality=Quality.HIGH,
        output_dir=str(tmp_path),
    )
    res = dl.download(job)
    assert res.success, res.error
    assert res.path.lower().endswith(".mp3")


@needs_live
def test_live_cancel_stops_the_job(tmp_path):
    import threading
    import time

    dl = Downloader(EngineConfig(output_dir=str(tmp_path)))
    job = DownloadJob(
        track=Track(id="live", title="live", webpage_url=LIVE_URL),
        quality=Quality.HIGH,
        output_dir=str(tmp_path),
    )
    t = threading.Thread(target=lambda: dl.download(job))
    t.start()
    time.sleep(1.5)
    dl.cancel_all()
    t.join(timeout=30)

    assert not t.is_alive(), "download did not stop within 30s"
    assert dl.active_count == 0
