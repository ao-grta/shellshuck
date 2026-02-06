"""Dialog for creating/editing SSHFS mount configurations."""

from __future__ import annotations

import uuid

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from shellshuck.models import MountConfig


class MountDialog(QDialog):
    """Dialog for creating or editing a mount config."""

    def __init__(
        self,
        mount: MountConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mount = mount
        self._editing = mount is not None
        self.setWindowTitle("Edit Mount" if self._editing else "Add Mount")
        self.setMinimumWidth(500)

        self._setup_ui()
        if mount:
            self._populate(mount)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. NAS Home")
        form.addRow("Name:", self._name)

        self._host = QLineEdit()
        self._host.setPlaceholderText("e.g. nas.local")
        form.addRow("Host:", self._host)

        self._user = QLineEdit()
        self._user.setPlaceholderText("e.g. alice")
        form.addRow("User:", self._user)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(22)
        form.addRow("SSH Port:", self._port)

        self._remote_path = QLineEdit()
        self._remote_path.setPlaceholderText("e.g. /home/alice")
        form.addRow("Remote path:", self._remote_path)

        # Local mount point with browse button
        mount_row = QHBoxLayout()
        self._local_mount = QLineEdit()
        self._local_mount.setPlaceholderText("e.g. /mnt/nas")
        mount_row.addWidget(self._local_mount)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_mount_point)
        mount_row.addWidget(browse_btn)
        form.addRow("Local mount:", mount_row)

        self._sshfs_flags = QLineEdit()
        self._sshfs_flags.setPlaceholderText("e.g. -o allow_other")
        form.addRow("Extra SSHFS flags:", self._sshfs_flags)

        # SSH key row
        key_row = QHBoxLayout()
        self._identity_file = QLineEdit()
        self._identity_file.setReadOnly(True)
        self._identity_file.setPlaceholderText("Using SSH agent")
        key_row.addWidget(self._identity_file)
        setup_key_btn = QPushButton("Setup SSH Key")
        setup_key_btn.clicked.connect(self._on_setup_key)
        key_row.addWidget(setup_key_btn)
        form.addRow("SSH Key:", key_row)

        self._connect_on_startup = QCheckBox("Connect on startup")
        form.addRow("", self._connect_on_startup)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_setup_key(self) -> None:
        from shellshuck.widgets.key_setup_dialog import KeySetupDialog

        host = self._host.text().strip()
        user = self._user.text().strip()
        port = self._port.value()
        name = self._name.text().strip() or "mount"

        if not host or not user:
            return

        dialog = KeySetupDialog(name, host, user, port, parent=self)
        if dialog.run() and dialog.key_path:
            self._identity_file.setText(dialog.key_path)

    def _populate(self, mount: MountConfig) -> None:
        self._name.setText(mount.name)
        self._host.setText(mount.host)
        self._user.setText(mount.user)
        self._port.setValue(mount.port)
        self._remote_path.setText(mount.remote_path)
        self._local_mount.setText(mount.local_mount)
        self._sshfs_flags.setText(mount.sshfs_flags)
        self._identity_file.setText(mount.identity_file)
        self._connect_on_startup.setChecked(mount.connect_on_startup)

    def _browse_mount_point(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Mount Point", self._local_mount.text()
        )
        if directory:
            self._local_mount.setText(directory)

    def get_config(self) -> MountConfig:
        """Return a MountConfig from the current form values."""
        return MountConfig(
            id=self._mount.id if self._mount else str(uuid.uuid4()),
            name=self._name.text().strip(),
            host=self._host.text().strip(),
            user=self._user.text().strip(),
            port=self._port.value(),
            remote_path=self._remote_path.text().strip(),
            local_mount=self._local_mount.text().strip(),
            sshfs_flags=self._sshfs_flags.text().strip(),
            connect_on_startup=self._connect_on_startup.isChecked(),
            identity_file=self._identity_file.text().strip(),
        )

    def run(self) -> bool:
        """Show the dialog modally and return True if accepted."""
        return self.exec_() == QDialog.DialogCode.Accepted
