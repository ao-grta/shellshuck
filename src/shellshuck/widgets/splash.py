"""Splash screen shown on first launch."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QLabel,
    QVBoxLayout,
)

from shellshuck import __version__

LOGO_PATH = Path(__file__).parent.parent.parent.parent / "resources" / "icons" / "shellshuck.svg"


class SplashScreen(QDialog):
    """Frameless splash dialog with logo, version, and 'don't show again' option."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(360, 340)
        self.setStyleSheet(
            "QDialog { background: #2d2d2d; border-radius: 16px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 24)
        layout.setSpacing(8)

        # Logo
        logo = QSvgWidget(str(LOGO_PATH))
        logo.setFixedSize(120, 120)
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        # App name
        name_label = QLabel("Shellshuck")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(
            "color: #4caf50; font-size: 26px; font-weight: bold;"
            " font-family: monospace;"
        )
        layout.addWidget(name_label)

        # Tagline
        tagline = QLabel("SSH Tunnel & Mount Manager")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            "color: #b0b0b0; font-size: 13px; font-family: sans-serif;"
        )
        layout.addWidget(tagline)

        # Version
        version_label = QLabel(f"v{__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(
            "color: #777; font-size: 11px; font-family: monospace;"
        )
        layout.addWidget(version_label)

        layout.addSpacing(16)

        # Don't show again checkbox
        self._checkbox = QCheckBox("Don't show this again")
        self._checkbox.setStyleSheet(
            "QCheckBox { color: #999; font-size: 12px; }"
            " QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        layout.addWidget(self._checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(4)

        # Hint
        hint = QLabel("Click anywhere or press any key to continue")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            "color: #555; font-size: 10px; font-style: italic;"
        )
        layout.addWidget(hint)

    @property
    def dont_show_again(self) -> bool:
        """Whether the user checked 'don't show again'."""
        return self._checkbox.isChecked()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        self.accept()
