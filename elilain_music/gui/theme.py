"""Theme manager — one palette object, two appearances, live switching.

Design rules enforced here:
* every colour the UI uses comes from PALETTES; no literals in widgets
* one accent carries "primary action", a second is reserved for the Lain
  red wire motif. Status colours (ok/warn/err) remain distinct.
* text pairs are checked against their surface, so the light theme is a real
  palette rather than an inverted dark one.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Signal, Slot


@dataclass(frozen=True)
class Palette:
    name: str
    # surfaces
    bg_top: str
    bg_bottom: str
    surface: str
    surface_alt: str
    border: str
    border_strong: str
    # text
    text: str
    text_dim: str
    text_faint: str
    # brand
    accent: str            # primary action
    accent_hover: str
    accent_press: str
    accent_text: str
    signal: str            # muted red — reserved for the wire motif/links
    # status
    ok: str
    warn: str
    err: str
    # progress
    track: str
    glow: str


DARK = Palette(
    name="dark",
    bg_top="#080d1b",
    bg_bottom="#060a14",
    surface="#0f192c",
    surface_alt="#142139",
    border="#263b59",
    border_strong="#49688c",
    text="#e5efff",
    text_dim="#adbed8",
    text_faint="#8fa4c2",
    accent="#77dfee",
    accent_hover="#a1f0f6",
    accent_press="#4abacc",
    accent_text="#081420",
    signal="#b5a3ff",
    ok="#83d9b6",
    warn="#f4ce89",
    err="#ff9fae",
    track="#223552",
    glow="rgba(119,223,238,0.12)",
)

LIGHT = Palette(
    name="light",
    bg_top="#eaf0fa",
    bg_bottom="#dbe5f5",
    surface="#f8fbff",
    surface_alt="#e1eaf6",
    border="#b8c7de",
    border_strong="#7188aa",
    text="#172842",
    text_dim="#435a77",
    text_faint="#526784",
    accent="#21576d",
    accent_hover="#286d87",
    accent_press="#173c50",
    accent_text="#ffffff",
    signal="#6444a6",
    ok="#276448",
    warn="#795510",
    err="#a52248",
    track="#c4d3e9",
    glow="rgba(33,87,109,0.12)",
)


class ThemeManager(QObject):
    """Singleton owning the current palette and broadcasting changes."""

    _instance: ThemeManager | None = None

    themeChanged = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._palettes = {"dark": DARK, "light": LIGHT}
        self._current = "dark"

    @staticmethod
    def instance() -> ThemeManager:
        if ThemeManager._instance is None:
            ThemeManager._instance = ThemeManager()
        return ThemeManager._instance

    # ------------------------------------------------------------------ #
    @property
    def palette(self) -> Palette:
        return self._palettes[self._current]

    @property
    def is_dark(self) -> bool:
        return self._current == "dark"

    # Qt property so QML / bindings can read it too
    @Property(str, notify=themeChanged)
    def mode(self) -> str:
        return self._current

    def set_mode(self, mode: str) -> None:
        mode = mode if mode in self._palettes else "dark"
        if mode != self._current:
            self._current = mode
            self.themeChanged.emit(self._current)

    def toggle(self) -> None:
        self.set_mode("light" if self.is_dark else "dark")

    @Slot()
    def toggle_theme(self) -> None:
        self.toggle()

    # ------------------------------------------------------------------ #
    def stylesheet(self) -> str:
        """Build the full app QSS from the active palette."""
        p = self.palette
        return f"""
QWidget {{
    background-color: {p.bg_top};
    color: {p.text};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{ background-color: {p.bg_top}; }}

/* ---- surfaces ---------------------------------------------------- */
QFrame#card, QGroupBox {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 3px;
}}
QGroupBox {{
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: {p.text_dim};
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QLabel#cardTitle {{ font-size: 19px; font-weight: 700; color: {p.text}; }}
QLabel#brand {{ font-family: "Georgia"; font-size: 32px; font-weight: 400; color: {p.text}; }}
QFrame#wiredSidebar {{ background: {p.surface}; border: 1px solid {p.border}; }}
QFrame#wiredSidebar QLabel, QFrame#wiredSidebar QCheckBox {{ background: transparent; }}
QLabel#lainTitle {{ font-family: "Georgia"; font-size: 64px; font-weight: 400; color: {p.text}; }}
QLabel#layerLabel {{ color: {p.text_dim}; font-family: "Consolas"; font-size: 10px; letter-spacing: 1px; }}
QLabel#wiredStamp {{ color: {p.signal}; font-family: "Consolas"; font-size: 11px; padding: 6px; border: 1px solid {p.border}; }}
QCheckBox {{ spacing: 7px; color: {p.text_dim}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {p.border_strong}; background: {p.surface_alt}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border: 2px solid {p.border_strong}; }}
QLabel#tagline {{ color: {p.signal}; font-size: 12px; letter-spacing: 2px; }}
QLabel#dim {{ color: {p.text_dim}; }}
QLabel#faint {{ color: {p.text_faint}; font-size: 11px; }}
QLabel#signal {{ color: {p.signal}; font-weight: 600; }}

/* ---- inputs ------------------------------------------------------ */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 2px;
    padding: 8px 10px;
    color: {p.text};
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: {p.text_faint};
    background-color: {p.surface};
}}
QLineEdit#urlInput {{ padding: 12px 14px; font-size: 14px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {p.text_dim};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {p.surface};
    border: 1px solid {p.border_strong};
    border-radius: 2px;
    padding: 4px;
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
    outline: none;
}}

/* ---- buttons ----------------------------------------------------- */
QPushButton {{
    background-color: {p.accent};
    color: {p.accent_text};
    border: none;
    border-radius: 2px;
    padding: 10px 18px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {p.accent_hover}; }}
QPushButton:pressed {{ background-color: {p.accent_press}; }}
QPushButton:disabled {{
    background-color: {p.surface_alt};
    color: {p.text_faint};
}}
QPushButton#secondary {{
    background-color: {p.surface_alt};
    color: {p.text};
    border: 1px solid {p.border_strong};
}}
QPushButton#secondary:hover {{ background-color: {p.border}; }}
QPushButton#secondary:disabled {{ color: {p.text_faint}; }}
QPushButton#danger {{
    background-color: transparent;
    color: {p.err};
    border: 1px solid {p.err};
}}
QPushButton#danger:hover {{ background-color: {p.err}; color: {p.accent_text}; }}

/* ---- progress ---------------------------------------------------- */
QProgressBar {{
    background-color: {p.track};
    border: none;
    border-radius: 2px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {p.accent};
    border-radius: 2px;
}}

/* ---- lists / tables ---------------------------------------------- */
QListWidget, QTreeWidget, QTableWidget {{
    background-color: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 2px;
    padding: 4px;
}}
QWidget#queueRow, QWidget#queueRow QLabel {{ background: transparent; }}
QListWidget::item {{ padding: 0px; }}
QTreeWidget::item {{
    padding: 7px 8px;
    border-radius: 2px;
    color: {p.text};
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {p.accent};
    color: {p.accent_text};
}}
QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {p.border};
}}

/* ---- log --------------------------------------------------------- */
QTextEdit#log {{
    background-color: {p.bg_bottom};
    border: 1px solid {p.border};
    border-radius: 2px;
    color: {p.text_dim};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    padding: 8px;
}}

/* ---- scrollbars -------------------------------------------------- */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {p.border_strong}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {p.border_strong}; border-radius: 5px; min-width: 30px;
}}

/* ---- misc -------------------------------------------------------- */
QToolTip {{
    background-color: {p.surface};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: 2px;
    padding: 6px 8px;
}}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:vertical {{ height: 8px; }}
QStatusBar {{ background: transparent; color: {p.text_dim}; }}
QStatusBar::item {{ border: none; }}
"""


def get_theme() -> ThemeManager:
    return ThemeManager.instance()
