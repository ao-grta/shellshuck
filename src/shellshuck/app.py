"""Application setup and orchestration."""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QCloseEvent, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from shellshuck.config import ConfigManager
from shellshuck.managers.mount import MountManager, MountState
from shellshuck.managers.tunnel import TunnelManager, TunnelState
from shellshuck.models import MountConfig, TunnelConfig
from shellshuck.resources import get_resources_dir
from shellshuck.widgets.main_window import MainWindow

logger = logging.getLogger(__name__)

RESOURCES_DIR = get_resources_dir()


def _make_circle_icon(color: QColor) -> QIcon:
    """Generate a simple colored circle icon for the system tray."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(color)
    painter.setPen(color)
    painter.drawEllipse(4, 4, 56, 56)
    painter.end()
    return QIcon(pixmap)


class _CloseToTrayMainWindow(MainWindow):
    """MainWindow subclass that hides to tray on close instead of quitting."""

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802  # type: ignore[override]
        if QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)


class ShellshuckApp:
    """Top-level application coordinator."""

    def __init__(self) -> None:
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName("Shellshuck")
        # Don't quit when window closes — tray keeps app alive
        self.qt_app.setQuitOnLastWindowClosed(False)

        # Set application window icon
        logo_path = RESOURCES_DIR / "shellshuck.svg"
        if logo_path.exists():
            self.qt_app.setWindowIcon(QIcon(str(logo_path)))

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()

        self.tunnel_manager = TunnelManager()
        self.mount_manager = MountManager()

        self.main_window = _CloseToTrayMainWindow(
            config=self.config,
            tunnel_manager=self.tunnel_manager,
            mount_manager=self.mount_manager,
        )

        self._setup_tray()
        self._connect_signals()
        self._autoconnect()

    def _setup_tray(self) -> None:
        """Set up the system tray icon and menu."""
        self._icon_ok = self._load_icon("tray-ok.svg", QColor(76, 175, 80))
        self._icon_error = self._load_icon("tray-error.svg", QColor(244, 67, 54))
        self._icon_idle = self._load_icon("tray-idle.svg", QColor(158, 158, 158))

        self._tray = QSystemTrayIcon(self._icon_idle)
        self._tray.setToolTip("Shellshuck")

        menu = QMenu()
        menu.addAction("Connect All", self._connect_all)
        menu.addAction("Disconnect All", self._disconnect_all)
        menu.addSeparator()
        menu.addAction("Open Window", self._show_window)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _connect_signals(self) -> None:
        self.main_window.add_tunnel_requested.connect(self._on_add_tunnel)
        self.main_window.add_mount_requested.connect(self._on_add_mount)
        self.main_window.edit_tunnel_requested.connect(self._on_edit_tunnel)
        self.main_window.edit_mount_requested.connect(self._on_edit_mount)
        self.main_window.delete_requested.connect(self._on_delete)
        self.main_window.setup_key_requested.connect(self._on_setup_key)

        # Wire manager log signals to the log panel
        log_panel = self.main_window.log_panel
        self.tunnel_manager.tunnel_log.connect(
            lambda cid, msg: log_panel.add_log(cid, msg, self._name_for_id(cid))
        )
        self.mount_manager.mount_log.connect(
            lambda cid, msg: log_panel.add_log(cid, msg, self._name_for_id(cid))
        )

        # Update tray icon on state changes
        self.tunnel_manager.tunnel_state_changed.connect(lambda *_: self._update_tray_icon())
        self.mount_manager.mount_state_changed.connect(lambda *_: self._update_tray_icon())

        # Desktop notifications on errors
        self.tunnel_manager.tunnel_error.connect(self._notify_error)
        self.mount_manager.mount_error.connect(self._notify_error)

    def _autoconnect(self) -> None:
        """Connect tunnels and mounts marked for auto-connect on startup."""
        for t in self.config.tunnels:
            if t.connect_on_startup:
                self.tunnel_manager.start(t)
        for m in self.config.mounts:
            if m.connect_on_startup:
                self.mount_manager.mount(m)

    def _save_and_refresh(self) -> None:
        self.config_manager.save(self.config)
        self.main_window.set_config(self.config)

    def _on_add_tunnel(self) -> None:
        from shellshuck.widgets.tunnel_dialog import TunnelDialog

        dialog = TunnelDialog(parent=self.main_window)
        if dialog.run():
            tunnel = dialog.get_config()
            self.config.tunnels.append(tunnel)
            self._save_and_refresh()

    def _on_add_mount(self) -> None:
        from shellshuck.widgets.mount_dialog import MountDialog

        dialog = MountDialog(parent=self.main_window)
        if dialog.run():
            mount = dialog.get_config()
            self.config.mounts.append(mount)
            self._save_and_refresh()

    def _on_edit_tunnel(self, config_id: str) -> None:
        from shellshuck.widgets.tunnel_dialog import TunnelDialog

        tunnel = self._find_tunnel(config_id)
        if tunnel is None:
            return
        dialog = TunnelDialog(tunnel=tunnel, parent=self.main_window)
        if dialog.run():
            updated = dialog.get_config()
            for i, t in enumerate(self.config.tunnels):
                if t.id == config_id:
                    self.config.tunnels[i] = updated
                    break
            self._save_and_refresh()

    def _on_edit_mount(self, config_id: str) -> None:
        from shellshuck.widgets.mount_dialog import MountDialog

        mount = self._find_mount(config_id)
        if mount is None:
            return
        dialog = MountDialog(mount=mount, parent=self.main_window)
        if dialog.run():
            updated = dialog.get_config()
            for i, m in enumerate(self.config.mounts):
                if m.id == config_id:
                    self.config.mounts[i] = updated
                    break
            self._save_and_refresh()

    def _on_delete(self, config_id: str, conn_type: str) -> None:
        reply = QMessageBox.question(
            self.main_window,
            "Delete Connection",
            "Are you sure you want to delete this connection?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if conn_type == "tunnel":
            self.tunnel_manager.stop(config_id)
            self.config.tunnels = [t for t in self.config.tunnels if t.id != config_id]
        else:
            self.mount_manager.unmount(config_id)
            self.config.mounts = [m for m in self.config.mounts if m.id != config_id]

        self._save_and_refresh()

    def _on_setup_key(self, config_id: str, conn_type: str) -> None:
        from shellshuck.widgets.key_setup_dialog import KeySetupDialog

        if conn_type == "tunnel":
            config = self._find_tunnel(config_id)
        else:
            config = self._find_mount(config_id)

        if config is None:
            return

        dialog = KeySetupDialog(
            name=config.name,
            host=config.host,
            user=config.user,
            port=config.port,
            parent=self.main_window,
        )
        if dialog.run() and dialog.key_path:
            config.identity_file = dialog.key_path
            self._save_and_refresh()

    # --- Tray ---

    @staticmethod
    def _load_icon(svg_name: str, fallback_color: QColor) -> QIcon:
        """Load an SVG icon, falling back to a generated circle."""
        svg_path = RESOURCES_DIR / svg_name
        if svg_path.exists():
            return QIcon(str(svg_path))
        return _make_circle_icon(fallback_color)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()

    def _show_window(self) -> None:
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _connect_all(self) -> None:
        for t in self.config.tunnels:
            self.tunnel_manager.start(t)
        for m in self.config.mounts:
            self.mount_manager.mount(m)

    def _disconnect_all(self) -> None:
        self.tunnel_manager.stop_all()
        self.mount_manager.unmount_all()

    def _quit(self) -> None:
        self.tunnel_manager.stop_all()
        self.mount_manager.unmount_all()
        self._tray.hide()
        self.qt_app.quit()

    def _update_tray_icon(self) -> None:
        """Update tray icon based on overall connection health."""
        has_error = False
        has_connected = False

        for tp in self.tunnel_manager.tunnels.values():
            if tp.state in (TunnelState.ERROR, TunnelState.RECONNECTING):
                has_error = True
            elif tp.state == TunnelState.CONNECTED:
                has_connected = True

        for mp in self.mount_manager.mounts.values():
            if mp.state in (MountState.ERROR, MountState.UNHEALTHY, MountState.RECONNECTING):
                has_error = True
            elif mp.state == MountState.MOUNTED:
                has_connected = True

        if has_error:
            self._tray.setIcon(self._icon_error)
        elif has_connected:
            self._tray.setIcon(self._icon_ok)
        else:
            self._tray.setIcon(self._icon_idle)

    def _notify_error(self, config_id: str, error_msg: str) -> None:
        """Show a desktop notification for connection errors."""
        name = self._name_for_id(config_id)
        if self._tray.supportsMessages():
            self._tray.showMessage(
                f"Shellshuck — {name}",
                error_msg,
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )

    # --- Helpers ---

    def _name_for_id(self, config_id: str) -> str:
        """Look up a human-readable name for a config id."""
        for t in self.config.tunnels:
            if t.id == config_id:
                return t.name
        for m in self.config.mounts:
            if m.id == config_id:
                return m.name
        return config_id[:8]

    def _find_tunnel(self, config_id: str) -> TunnelConfig | None:
        for t in self.config.tunnels:
            if t.id == config_id:
                return t
        return None

    def _find_mount(self, config_id: str) -> MountConfig | None:
        for m in self.config.mounts:
            if m.id == config_id:
                return m
        return None

    def run(self) -> int:
        if self.config.show_splash:
            from shellshuck.widgets.splash import SplashScreen

            splash = SplashScreen()
            splash.exec_()
            if splash.dont_show_again:
                self.config.show_splash = False
                self.config_manager.save(self.config)

        self.main_window.show()
        return self.qt_app.exec_()
