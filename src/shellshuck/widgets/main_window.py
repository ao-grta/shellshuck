"""Main window with connection list and controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMainWindow,
    QMenu,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QWidget,
)

from shellshuck.managers.mount import MountManager, MountState
from shellshuck.managers.tunnel import TunnelManager, TunnelState
from shellshuck.models import AppConfig, MountConfig, TunnelConfig
from shellshuck.widgets.log_panel import LogPanel

STATE_COLORS = {
    "connected": QColor(76, 175, 80),
    "disconnected": QColor(158, 158, 158),
    "connecting": QColor(255, 193, 7),
    "reconnecting": QColor(255, 152, 0),
    "error": QColor(244, 67, 54),
    "unhealthy": QColor(255, 87, 34),
}


def _tunnel_state_label(state: TunnelState) -> tuple[str, QColor]:
    mapping = {
        TunnelState.DISCONNECTED: ("Disconnected", STATE_COLORS["disconnected"]),
        TunnelState.CONNECTING: ("Connecting...", STATE_COLORS["connecting"]),
        TunnelState.CONNECTED: ("Connected", STATE_COLORS["connected"]),
        TunnelState.RECONNECTING: ("Reconnecting...", STATE_COLORS["reconnecting"]),
        TunnelState.ERROR: ("Error", STATE_COLORS["error"]),
    }
    return mapping.get(state, ("Unknown", STATE_COLORS["disconnected"]))


def _mount_state_label(state: MountState) -> tuple[str, QColor]:
    mapping = {
        MountState.UNMOUNTED: ("Unmounted", STATE_COLORS["disconnected"]),
        MountState.MOUNTING: ("Mounting...", STATE_COLORS["connecting"]),
        MountState.MOUNTED: ("Mounted", STATE_COLORS["connected"]),
        MountState.UNHEALTHY: ("Unhealthy", STATE_COLORS["unhealthy"]),
        MountState.UNMOUNTING: ("Unmounting...", STATE_COLORS["connecting"]),
        MountState.RECONNECTING: ("Reconnecting...", STATE_COLORS["reconnecting"]),
        MountState.ERROR: ("Error", STATE_COLORS["error"]),
    }
    return mapping.get(state, ("Unknown", STATE_COLORS["disconnected"]))


COL_NAME = 0
COL_TYPE = 1
COL_TARGET = 2
COL_STATUS = 3


class MainWindow(QMainWindow):
    """Main application window with connection table."""

    add_tunnel_requested = Signal()
    add_mount_requested = Signal()
    edit_tunnel_requested = Signal(str)
    edit_mount_requested = Signal(str)
    delete_requested = Signal(str, str)

    def __init__(
        self,
        config: AppConfig,
        tunnel_manager: TunnelManager,
        mount_manager: MountManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._tunnel_manager = tunnel_manager
        self._mount_manager = mount_manager

        self.setWindowTitle("Shellshuck — SSH Manager")
        self.setMinimumSize(700, 400)

        self._setup_toolbar()
        self._setup_table()
        self._connect_signals()
        self.refresh_table()

    def set_config(self, config: AppConfig) -> None:
        """Update the config and refresh the table."""
        self._config = config
        self.refresh_table()

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        btn_add_tunnel = QPushButton("Add Tunnel")
        btn_add_tunnel.clicked.connect(self.add_tunnel_requested.emit)
        toolbar.addWidget(btn_add_tunnel)

        btn_add_mount = QPushButton("Add Mount")
        btn_add_mount.clicked.connect(self.add_mount_requested.emit)
        toolbar.addWidget(btn_add_mount)

        toolbar.addSeparator()

        btn_connect_all = QPushButton("Connect All")
        btn_connect_all.clicked.connect(self._connect_all)
        toolbar.addWidget(btn_connect_all)

        btn_disconnect_all = QPushButton("Disconnect All")
        btn_disconnect_all.clicked.connect(self._disconnect_all)
        toolbar.addWidget(btn_disconnect_all)

    def _setup_table(self) -> None:
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Name", "Type", "Target", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(
            COL_TARGET, QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.doubleClicked.connect(self._on_double_click)

        # Log panel
        self._log_panel = LogPanel()

        # Splitter: table on top, log panel on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._table)
        splitter.addWidget(self._log_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    @property
    def log_panel(self) -> LogPanel:
        return self._log_panel

    def _connect_signals(self) -> None:
        self._tunnel_manager.tunnel_state_changed.connect(self._on_tunnel_state_changed)
        self._mount_manager.mount_state_changed.connect(self._on_mount_state_changed)

    def refresh_table(self) -> None:
        """Rebuild the table from config + current states."""
        self._table.setRowCount(0)
        self._row_map: dict[int, tuple[str, str]] = {}

        row = 0
        for t in self._config.tunnels:
            self._table.insertRow(row)
            self._table.setItem(row, COL_NAME, QTableWidgetItem(t.name))
            self._table.setItem(row, COL_TYPE, QTableWidgetItem("Tunnel"))
            target = f"{t.user}@{t.host}:{t.port}"
            if t.forward_rules:
                forwards = ", ".join(r.to_ssh_arg() for r in t.forward_rules)
                target += f" [{forwards}]"
            self._table.setItem(row, COL_TARGET, QTableWidgetItem(target))
            state = self._tunnel_manager.get_state(t.id)
            label, color = _tunnel_state_label(state)
            status_item = QTableWidgetItem(label)
            status_item.setForeground(color)
            self._table.setItem(row, COL_STATUS, status_item)
            self._row_map[row] = (t.id, "tunnel")
            row += 1

        for m in self._config.mounts:
            self._table.insertRow(row)
            self._table.setItem(row, COL_NAME, QTableWidgetItem(m.name))
            self._table.setItem(row, COL_TYPE, QTableWidgetItem("Mount"))
            target = f"{m.user}@{m.host}:{m.remote_path} -> {m.local_mount}"
            self._table.setItem(row, COL_TARGET, QTableWidgetItem(target))
            state = self._mount_manager.get_state(m.id)
            label, color = _mount_state_label(state)
            status_item = QTableWidgetItem(label)
            status_item.setForeground(color)
            self._table.setItem(row, COL_STATUS, status_item)
            self._row_map[row] = (m.id, "mount")
            row += 1

    def _on_tunnel_state_changed(self, config_id: str, state: TunnelState) -> None:
        self._update_status_for(config_id, *_tunnel_state_label(state))

    def _on_mount_state_changed(self, config_id: str, state: MountState) -> None:
        self._update_status_for(config_id, *_mount_state_label(state))

    def _update_status_for(self, config_id: str, label: str, color: QColor) -> None:
        for row, (cid, _) in self._row_map.items():
            if cid == config_id:
                item = QTableWidgetItem(label)
                item.setForeground(color)
                self._table.setItem(row, COL_STATUS, item)
                break

    def _get_row_info(self, row: int) -> tuple[str, str] | None:
        return self._row_map.get(row)

    def _show_context_menu(self, pos: object) -> None:
        row = self._table.currentRow()
        info = self._get_row_info(row)
        if info is None:
            return
        config_id, conn_type = info

        menu = QMenu(self)

        if conn_type == "tunnel":
            state = self._tunnel_manager.get_state(config_id)
            if state in (TunnelState.CONNECTED, TunnelState.CONNECTING, TunnelState.RECONNECTING):
                menu.addAction("Disconnect", lambda: self._tunnel_manager.stop(config_id))
            else:
                config = self._find_tunnel(config_id)
                if config:
                    menu.addAction("Connect", lambda: self._tunnel_manager.start(config))
            menu.addAction("Edit", lambda: self.edit_tunnel_requested.emit(config_id))
        else:
            state = self._mount_manager.get_state(config_id)
            if state in (MountState.MOUNTED, MountState.MOUNTING, MountState.RECONNECTING):
                menu.addAction("Disconnect", lambda: self._mount_manager.unmount(config_id))
            else:
                config = self._find_mount(config_id)
                if config:
                    menu.addAction("Connect", lambda: self._mount_manager.mount(config))
            menu.addAction("Edit", lambda: self.edit_mount_requested.emit(config_id))

        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete_requested.emit(config_id, conn_type))

        menu.popup(self._table.viewport().mapToGlobal(pos))  # type: ignore[arg-type]

    def _on_double_click(self, index: object) -> None:
        row = self._table.currentRow()
        info = self._get_row_info(row)
        if info is None:
            return
        config_id, conn_type = info

        if conn_type == "tunnel":
            state = self._tunnel_manager.get_state(config_id)
            if state in (TunnelState.CONNECTED, TunnelState.CONNECTING, TunnelState.RECONNECTING):
                self._tunnel_manager.stop(config_id)
            else:
                config = self._find_tunnel(config_id)
                if config:
                    self._tunnel_manager.start(config)
        else:
            state = self._mount_manager.get_state(config_id)
            if state in (MountState.MOUNTED, MountState.MOUNTING, MountState.RECONNECTING):
                self._mount_manager.unmount(config_id)
            else:
                config = self._find_mount(config_id)
                if config:
                    self._mount_manager.mount(config)

    def _connect_all(self) -> None:
        for t in self._config.tunnels:
            self._tunnel_manager.start(t)
        for m in self._config.mounts:
            self._mount_manager.mount(m)

    def _disconnect_all(self) -> None:
        self._tunnel_manager.stop_all()
        self._mount_manager.unmount_all()

    def _find_tunnel(self, config_id: str) -> TunnelConfig | None:
        for t in self._config.tunnels:
            if t.id == config_id:
                return t
        return None

    def _find_mount(self, config_id: str) -> MountConfig | None:
        for m in self._config.mounts:
            if m.id == config_id:
                return m
        return None
