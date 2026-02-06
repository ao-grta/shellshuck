"""Per-connection log panel widget."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogPanel(QWidget):
    """Collapsible log panel showing timestamped events per connection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # logs[config_id] = list of "(timestamp) message"
        self._logs: dict[str, list[str]] = {}
        self._current_id: str | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header row: connection selector + clear button
        header = QHBoxLayout()

        self._selector = QComboBox()
        self._selector.addItem("All connections", "")
        self._selector.currentIndexChanged.connect(self._on_selection_changed)
        header.addWidget(self._selector, stretch=1)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_current)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # Log display
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFontFamily("monospace")
        self._text.setMaximumHeight(200)
        layout.addWidget(self._text)

    def add_log(self, config_id: str, message: str, config_name: str | None = None) -> None:
        """Append a log entry for a connection."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"

        if config_id not in self._logs:
            self._logs[config_id] = []
            display_name = config_name or config_id[:8]
            self._selector.addItem(display_name, config_id)

        self._logs[config_id].append(entry)

        # If currently viewing this connection or "All", append to display
        selected_id = self._selector.currentData()
        if selected_id == "" or selected_id == config_id:
            prefix = f"[{config_name or config_id[:8]}] " if selected_id == "" else ""
            self._text.append(f"{prefix}{entry}")

    def _on_selection_changed(self, index: int) -> None:
        """Refresh display when the connection filter changes."""
        self._text.clear()
        selected_id = self._selector.currentData()

        if selected_id == "":
            # Show all logs interleaved (by insertion order per-connection)
            for cid, entries in self._logs.items():
                name = self._name_for_id(cid)
                for entry in entries:
                    self._text.append(f"[{name}] {entry}")
        elif selected_id in self._logs:
            for entry in self._logs[selected_id]:
                self._text.append(entry)

    def _clear_current(self) -> None:
        """Clear logs for the currently selected connection."""
        selected_id = self._selector.currentData()
        if selected_id == "":
            self._logs.clear()
        elif selected_id in self._logs:
            self._logs[selected_id].clear()
        self._text.clear()

    def _name_for_id(self, config_id: str) -> str:
        for i in range(self._selector.count()):
            if self._selector.itemData(i) == config_id:
                return self._selector.itemText(i)
        return config_id[:8]
