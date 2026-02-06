"""Dialog that generates and deploys an SSH key for a connection."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from shellshuck.key_manager import deploy_key, generate_key

logger = logging.getLogger(__name__)

KEYS_DIR = Path.home() / ".config" / "shellshuck" / "keys"


class KeySetupDialog(QDialog):
    """Orchestrates SSH key generation and deployment."""

    def __init__(
        self,
        name: str,
        host: str,
        user: str,
        port: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._host = host
        self._user = user
        self._port = port
        self._key_path: str = ""
        self._deploy_process: QProcess | None = None
        self._stderr_buffer: str = ""

        self.setWindowTitle("Setup SSH Key")
        self.setMinimumWidth(420)
        self._setup_ui()
        self._run_setup()

    @property
    def key_path(self) -> str:
        """Return the generated private key path, or empty on failure."""
        return self._key_path

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._info_label = QLabel(
            f"Setting up SSH key for <b>{self._user}@{self._host}:{self._port}</b>"
        )
        layout.addWidget(self._info_label)

        self._step1_label = QLabel("Step 1: Generate keypair...")
        layout.addWidget(self._step1_label)

        self._step2_label = QLabel("Step 2: Deploy public key...")
        layout.addWidget(self._step2_label)

        self._result_label = QLabel("")
        layout.addWidget(self._result_label)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self._on_cancel)
        layout.addWidget(self._buttons)

    def _run_setup(self) -> None:
        """Step 1: generate the key synchronously."""
        try:
            key_path = generate_key(self._name, KEYS_DIR)
        except (RuntimeError, OSError) as exc:
            self._step1_label.setText(f"Step 1: FAILED — {exc}")
            self._result_label.setText("Key generation failed.")
            return

        self._key_path = str(key_path)
        self._step1_label.setText("Step 1: Generated keypair \u2714")

        # Step 2: deploy
        pub_path = Path(self._key_path + ".pub")
        self._step2_label.setText("Step 2: Deploying public key (enter password)...")

        process = deploy_key(pub_path, self._host, self._user, self._port, self)
        self._deploy_process = process
        self._stderr_buffer = ""

        process.readyReadStandardError.connect(self._on_stderr)
        process.finished.connect(self._on_deploy_finished)
        process.start()

    def _on_stderr(self) -> None:
        if self._deploy_process is None:
            return
        data = self._deploy_process.readAllStandardError().data().decode(
            errors="replace"
        )
        self._stderr_buffer += data

    def _on_deploy_finished(self, exit_code: int, _status: object) -> None:
        if exit_code == 0:
            self._step2_label.setText("Step 2: Public key deployed \u2714")
            self._result_label.setText(f"Key: {self._key_path}")
            self._buttons.button(
                QDialogButtonBox.StandardButton.Ok
            ).setEnabled(True)
        else:
            # Trim stderr for display
            err = self._stderr_buffer.strip().splitlines()
            err_msg = err[-1] if err else "Unknown error"
            self._step2_label.setText("Step 2: Deployment FAILED")
            self._result_label.setText(f"Error: {err_msg}")
            self._key_path = ""

    def _on_cancel(self) -> None:
        if (
            self._deploy_process is not None
            and self._deploy_process.state() != QProcess.ProcessState.NotRunning
        ):
            self._deploy_process.kill()
        self._key_path = ""
        self.reject()

    def run(self) -> bool:
        """Show the dialog modally and return True if accepted."""
        return self.exec_() == QDialog.DialogCode.Accepted
