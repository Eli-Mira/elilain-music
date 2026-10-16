"""Serve the real dashboard on loopback with isolated QA preferences."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from elilain_music.gui import settings

out = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "cache" / "scratch" / "elilain-browser-preview"
out.mkdir(parents=True, exist_ok=True)
settings.CONFIG_DIR = out
settings.CONFIG_FILE = out / "browser-settings.json"
prefs = settings.Settings()
prefs.update(theme="dark", output_dir=str(out / "downloads"))
prefs.save()

from elilain_music.web.main import create_app  # noqa: E402 — isolate settings before import

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("127.0.0.1", 0))
url = f"http://127.0.0.1:{sock.getsockname()[1]}"
(out / "server-url.txt").write_text(url, encoding="utf-8")
print("QA dashboard " + url, flush=True)
server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", log_level="warning"))
server.run(sockets=[sock])
