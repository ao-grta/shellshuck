"""Resource path helpers for development and PyInstaller bundle modes."""

from __future__ import annotations

import sys
from pathlib import Path


def get_resources_dir() -> Path:
    """Return the path to the resources/icons directory.

    In a PyInstaller bundle, resources are extracted to sys._MEIPASS.
    In development, they live relative to the project root.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "resources" / "icons"  # type: ignore[attr-defined]
    return Path(__file__).parent.parent.parent / "resources" / "icons"


def get_askpass_path() -> str:
    """Return the path to the askpass helper executable.

    When frozen (PyInstaller), the askpass binary sits next to the main executable.
    In development, it's the askpass.py script in the package directory.
    """
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).parent / "shellshuck-askpass")
    return str(Path(__file__).parent / "askpass.py")
