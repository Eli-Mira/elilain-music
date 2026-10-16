"""Quiet Wired identity: local series artwork, wire drawing and optional CRT motion.

Art is kept offline. See assets/CREDITS.md; the anime art is not MIT-licensed.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QVBoxLayout, QWidget

from .theme import get_theme

ART_DIR = Path(__file__).resolve().parent.parent / "assets"


class LainPortrait(QWidget):
    """Original series portrait with barely visible scanlines; no strobing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lainPortrait")
        self.setMinimumHeight(240)
        self.setMaximumHeight(340)
        self.setAccessibleName("Portrait of Lain Iwakura")
        self.setToolTip("Lain Iwakura — artwork from the official Serial Experiments Lain site")
        self._image = QPixmap(str(ART_DIR / "lain.png"))
        self._motion_enabled = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._advance)

    @property
    def has_artwork(self) -> bool:
        return not self._image.isNull()

    @property
    def motion_enabled(self) -> bool:
        return self._motion_enabled

    def set_motion(self, enabled: bool) -> None:
        self._motion_enabled = bool(enabled)
        if self._motion_enabled and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + 0.004) % 1.0
        self.update()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._motion_enabled:
            self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        p = get_theme().palette
        bounds = QRectF(self.rect())
        painter.fillRect(bounds, QColor(p.surface_alt))
        if self.has_artwork:
            # Preserve composition without stretching the character.
            image = self._image.scaled(self.size(), Qt.KeepAspectRatioByExpanding,
                                       Qt.SmoothTransformation)
            painter.drawPixmap((self.width() - image.width()) // 2,
                               (self.height() - image.height()) // 2, image)
        else:
            painter.setPen(QColor(p.text_dim))
            painter.drawText(self.rect(), Qt.AlignCenter, "IWAKURA LAIN")
        # Analog texture is confined to the artwork, never over controls/text.
        if self._motion_enabled:
            painter.setPen(QColor(10, 10, 9, 18))
            for y in range(0, self.height(), 4):
                painter.drawLine(0, y, self.width(), y)
            y = int(self._phase * self.height())
            painter.fillRect(0, y, self.width(), 2, QColor(245, 235, 212, 24))
        painter.setPen(QPen(QColor(p.border_strong), 1))
        painter.drawRect(bounds.adjusted(0, 0, -1, -1))
        painter.end()


class WireTrace(QWidget):
    """Power-line silhouette, not a fake live signal or metric."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(66)
        self.setAccessibleName("Decorative overhead wire silhouette")

    def paintEvent(self, event) -> None:  # noqa: N802
        p = get_theme().palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(p.surface))
        painter.setPen(QPen(QColor(p.border_strong), 1))
        width = self.width()
        for offset in (0, 8, 16):
            path = QPainterPath()
            path.moveTo(-10, 4 + offset)
            path.cubicTo(width * 0.36, 48 + offset, width * 0.72, 16 + offset,
                         width + 8, 26 + offset)
            painter.drawPath(path)
        painter.setPen(QPen(QColor(p.text_dim), 2))
        x = width * 0.69
        painter.drawLine(int(x), 5, int(x), 66)
        painter.drawLine(int(x - 22), 14, int(x + 22), 14)
        painter.end()


class WiredSidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("wiredSidebar")
        self.setFixedWidth(250)
        col = QVBoxLayout(self)
        col.setContentsMargins(17, 18, 17, 17)
        col.setSpacing(12)
        serial = QLabel("SERIAL EXPERIMENTS")
        serial.setObjectName("layerLabel")
        col.addWidget(serial)
        title = QLabel("lain.")
        title.setObjectName("lainTitle")
        col.addWidget(title)
        identity = QLabel("岩倉玲音  /  IWAKURA LAIN")
        identity.setObjectName("layerLabel")
        col.addWidget(identity)
        self.portrait = LainPortrait(self)
        col.addWidget(self.portrait, 1)
        caption = QLabel("REAL WORLD  ↔  WIRED")
        caption.setObjectName("layerLabel")
        col.addWidget(caption)
        col.addWidget(WireTrace())
        scene = QLabel()
        scene.setObjectName("wiredScene")
        scene.setPixmap(QPixmap(str(ART_DIR / "wired-city.png")).scaledToWidth(
            216, Qt.SmoothTransformation))
        scene.setFixedHeight(116)
        scene.setAlignment(Qt.AlignCenter)
        scene.setToolTip("Series artwork — Serial Experiments Lain official website")
        col.addWidget(scene)
        note = QLabel("A quiet place for your music.\nSaved here. Not in the cloud.")
        note.setObjectName("dim")
        note.setWordWrap(True)
        col.addWidget(note)
        col.addStretch()
        self.motion_toggle = QCheckBox("CRT motion")
        self.motion_toggle.setObjectName("motionToggle")
        self.motion_toggle.setToolTip("Subtle scanline motion, confined to the portrait. Switch off for a still image.")
        self.motion_toggle.toggled.connect(self.portrait.set_motion)
        col.addWidget(self.motion_toggle)
        credits = QLabel("Art: official series site · personal fan UI")
        credits.setObjectName("faint")
        credits.setWordWrap(True)
        credits.setToolTip("https://www.serial-experiments-lain.com/\nArtwork © its respective rights holders; not licensed under the app's MIT license.")
        col.addWidget(credits)
        get_theme().themeChanged.connect(self._refresh)

    def _refresh(self, _mode: str) -> None:
        self.portrait.update()
        self.update()
        for trace in self.findChildren(WireTrace):
            trace.update()
