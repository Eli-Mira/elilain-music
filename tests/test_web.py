"""API tests for the web dashboard — FastAPI TestClient, no server needed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from elilain_music.web.assets import render
from elilain_music.web.main import create_app


@pytest.fixture()
def client():
    return TestClient(create_app())


# ==================================================================== #
# health / meta
# ==================================================================== #
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["yt_dlp"]
    assert isinstance(body["ffmpeg"], bool)


def test_palettes_expose_both_modes(client):
    body = client.get("/api/palettes").json()
    assert set(body) == {"dark", "light"}
    assert body["dark"]["accent"] != body["light"]["accent"]
    # every palette must define the full token set the template substitutes
    for mode, pal in body.items():
        for key in ("bg_top", "surface", "text", "accent", "signal", "ok", "err"):
            assert pal.get(key), f"{mode}.{key} missing"


def test_theme_endpoint_roundtrips(client):
    assert client.post("/api/theme", json={"mode": "light"}).json()["theme"] == "light"
    assert client.post("/api/theme", json={"mode": "nonsense"}).json()["theme"] == "dark"


# ==================================================================== #
# index
# ==================================================================== #
def test_index_renders_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "EliLain-Music" in r.text


def test_index_has_no_unsubstituted_placeholders(client):
    html = client.get("/").text
    assert "__" not in html.replace("__", "", 0) or "undefined" not in html
    # the template uses __TOKEN__ markers; none may survive rendering
    for marker in ("__BG_TOP__", "__ACCENT__", "__MODE__", "__SIGNAL__"):
        assert marker not in html, f"{marker} left unsubstituted"


def test_render_switches_palette():
    dark = render("dark")
    light = render("light")
    assert dark != light
    from elilain_music.gui.theme import DARK, LIGHT
    assert DARK.accent in dark
    assert LIGHT.accent in light


def test_index_uses_textcontent_not_innerhtml():
    """User input must reach the DOM only via textContent.

    Checks actual assignments, not the word "innerHTML" — the template mentions
    it in a comment explaining why it is avoided.
    """
    import re

    html = render("dark")
    # any `.innerHTML =` / `.innerHTML +=` assignment is a real sink
    assert not re.search(r"\.innerHTML\s*\+?=", html), "innerHTML assignment found"
    # outerHTML and document.write are equivalent sinks
    assert not re.search(r"\.outerHTML\s*\+?=", html), "outerHTML assignment found"
    assert "document.write" not in html
    # the rows are built with textContent
    assert re.search(r"\.textContent\s*=", html)


# ==================================================================== #
# jobs
# ==================================================================== #
def test_jobs_start_empty(client):
    assert client.get("/api/jobs").json()["jobs"] == []


def test_download_creates_a_job(client):
    r = client.post("/api/download", json={
        "url": "https://youtu.be/does-not-matter",
        "quality": "low",
    })
    assert r.status_code == 200
    job = r.json()
    assert job["state"] in ("queued", "running", "error", "done")
    assert job["quality"] == "low"
    assert job["id"]

    listed = client.get("/api/jobs").json()["jobs"]
    assert any(j["id"] == job["id"] for j in listed)


def test_download_rejects_empty_url(client):
    assert client.post("/api/download", json={"url": ""}).status_code == 422


def test_download_rejects_unknown_quality_by_falling_back(client):
    r = client.post("/api/download", json={"url": "https://youtu.be/x", "quality": "bogus"})
    assert r.status_code == 200
    assert r.json()["quality"] == "high"


def test_get_job_404s_for_unknown_id(client):
    assert client.get("/api/jobs/deadbeef").status_code == 404


def test_cancel_unknown_job_404s(client):
    assert client.post("/api/jobs/deadbeef/cancel").status_code == 404


def test_clear_finished_endpoint_exists(client):
    r = client.delete("/api/jobs/finished")
    assert r.status_code == 200
    assert "removed" in r.json()


def test_clear_all_jobs(client):
    client.post("/api/download", json={"url": "https://youtu.be/a"})
    client.post("/api/download", json={"url": "https://youtu.be/b"})
    assert client.delete("/api/jobs").json()["removed"] >= 2
    assert client.get("/api/jobs").json()["jobs"] == []


def test_job_public_shape_is_json_safe(client):
    client.post("/api/download", json={"url": "https://youtu.be/shape"})
    job = client.get("/api/jobs").json()["jobs"][0]
    for key in ("id", "url", "label", "quality", "state", "percent",
                "speed", "eta", "status_text", "path", "files", "error", "elapsed"):
        assert key in job
    assert isinstance(job["files"], list)
