"""Splash screen shown on first launch."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QLabel,
    QVBoxLayout,
)

from shellshuck import __version__

RESOURCES_DIR = Path(__file__).parent.parent.parent.parent / "resources" / "icons"
SPLASH_PATH = RESOURCES_DIR / "shellshuck-splash.png"


class SplashScreen(QDialog):
    """Frameless splash dialog with logo, version, and 'don't show again' option."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(400, 420)
        self.setStyleSheet(
            "QDialog { background: #2d2d2d; border-radius: 16px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 20)
        layout.setSpacing(6)

        # Logo from PNG
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(SPLASH_PATH))
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                240,
                240,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(scaled)
        layout.addWidget(logo_label)

        layout.addSpacing(4)

        # Version
        version_label = QLabel(f"v{__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(
            "color: #777; font-size: 11px; font-family: monospace;"
        )
        layout.addWidget(version_label)

        layout.addSpacing(12)

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
