"""Shared test fixtures."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import QCoreApplication


@pytest.fixture(scope="session")
def qapp() -> QCoreApplication:
    """Provide a QCoreApplication instance for tests needing Qt objects."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app
