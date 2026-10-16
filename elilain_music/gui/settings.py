"""Persisted settings — a tiny JSON store next to the user's music folder.

Kept deliberately dependency-free: one file, atomic write, corrupt-file
tolerant. Losing your theme preference to a stray KeyError is not acceptable.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger("elilain.settings")

CONFIG_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\EliLain-Music"))
CONFIG_FILE = CONFIG_DIR / "settings.json"

DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "crt_motion": False,
    "quality": "high",
    "parallel": 4,
    "fragments": 8,
    "output_dir": str(Path.home() / "Music" / "EliLain"),
    "embed_metadata": True,
    "embed_thumbnail": True,
    "overwrite": False,
    "last_inputs": [],
    "window_geometry": "",
}


class Settings:
    """Dict-like settings with atomic persistence."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else CONFIG_FILE
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    # ------------------------------------------------------------------ #
    def load(self) -> None:
        try:
            if self.path.is_file():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    # only accept known keys, so a hand-edited file can't inject junk
                    self._data.update({k: v for k, v in raw.items() if k in DEFAULTS})
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("settings unreadable (%s) — using defaults", exc)
        self._sanitize()

    def save(self) -> bool:
        """Atomic write — a crash mid-save must not corrupt the file."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except Exception:
                Path(tmp).unlink(missing_ok=True)
                raise
            return True
        except OSError as exc:
            log.warning("could not save settings: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    def _sanitize(self) -> None:
        d = self._data
        if d.get("theme") not in ("dark", "light"):
            d["theme"] = "dark"
        if d.get("quality") not in ("low", "medium", "high", "best", "lossless"):
            d["quality"] = "high"
        for key, lo, hi in (("parallel", 1, 8), ("fragments", 1, 16)):
            try:
                d[key] = max(lo, min(hi, int(d.get(key, lo))))
            except (TypeError, ValueError):
                d[key] = lo
        for key in ("embed_metadata", "embed_thumbnail", "overwrite", "crt_motion"):
            d[key] = bool(d.get(key))
        if not isinstance(d.get("last_inputs"), list):
            d["last_inputs"] = []
        d["last_inputs"] = [str(x)[:500] for x in d["last_inputs"][:20]]

    # ------------------------------------------------------------------ #
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, **kw: Any) -> None:
        self._data.update(kw)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self._sanitize()
