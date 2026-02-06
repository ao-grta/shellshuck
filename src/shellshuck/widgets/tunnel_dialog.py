"""Dialog for creating/editing SSH tunnel configurations."""

from __future__ import annotations

import uuid

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from shellshuck.models import ForwardRule, TunnelConfig


class ForwardRuleRow(QWidget):
    """A single row for editing a forwarding rule."""

    def __init__(self, rule: ForwardRule | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.local_port = QSpinBox()
        self.local_port.setRange(1, 65535)
        self.local_port.setValue(rule.local_port if rule else 8080)

        self.remote_host = QLineEdit(rule.remote_host if rule else "localhost")
        self.remote_host.setPlaceholderText("Remote host")

        self.remote_port = QSpinBox()
        self.remote_port.setRange(1, 65535)
        self.remote_port.setValue(rule.remote_port if rule else 80)

        self.remove_btn = QPushButton("Remove")

        layout.addWidget(QLabel("Local:"))
        layout.addWidget(self.local_port)
        layout.addWidget(QLabel("→"))
        layout.addWidget(self.remote_host)
        layout.addWidget(QLabel(":"))
        layout.addWidget(self.remote_port)
        layout.addWidget(self.remove_btn)

    def get_rule(self) -> ForwardRule:
        return ForwardRule(
            local_port=self.local_port.value(),
            remote_host=self.remote_host.text().strip() or "localhost",
            remote_port=self.remote_port.value(),
        )


class TunnelDialog(QDialog):
    """Dialog for creating or editing a tunnel config."""

    def __init__(
        self,
        tunnel: TunnelConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tunnel = tunnel
        self._editing = tunnel is not None
        self.setWindowTitle("Edit Tunnel" if self._editing else "Add Tunnel")
        self.setMinimumWidth(500)

        self._setup_ui()
        if tunnel:
            self._populate(tunnel)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Production DB")
        form.addRow("Name:", self._name)

        self._host = QLineEdit()
        self._host.setPlaceholderText("e.g. bastion.example.com")
        form.addRow("Host:", self._host)

        self._user = QLineEdit()
        self._user.setPlaceholderText("e.g. deploy")
        form.addRow("User:", self._user)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(22)
        form.addRow("SSH Port:", self._port)

        self._extra_flags = QLineEdit()
        self._extra_flags.setPlaceholderText("e.g. -o StrictHostKeyChecking=no")
        form.addRow("Extra SSH flags:", self._extra_flags)

        self._connect_on_startup = QCheckBox("Connect on startup")
        form.addRow("", self._connect_on_startup)

        layout.addLayout(form)

        # Forwarding rules
        rules_group = QGroupBox("Port Forwarding Rules (-L)")
        rules_layout = QVBoxLayout(rules_group)

        self._rules_container = QVBoxLayout()
        rules_layout.addLayout(self._rules_container)

        add_rule_btn = QPushButton("Add Rule")
        add_rule_btn.clicked.connect(self._add_rule_row)
        rules_layout.addWidget(add_rule_btn)

        layout.addWidget(rules_group)

        self._rule_rows: list[ForwardRuleRow] = []

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_rule_row(self, rule: ForwardRule | None = None) -> None:
        row = ForwardRuleRow(rule)
        row.remove_btn.clicked.connect(lambda: self._remove_rule_row(row))
        self._rules_container.addWidget(row)
        self._rule_rows.append(row)

    def _remove_rule_row(self, row: ForwardRuleRow) -> None:
        self._rules_container.removeWidget(row)
        self._rule_rows.remove(row)
        row.deleteLater()

    def _populate(self, tunnel: TunnelConfig) -> None:
        self._name.setText(tunnel.name)
        self._host.setText(tunnel.host)
        self._user.setText(tunnel.user)
        self._port.setValue(tunnel.port)
        self._extra_flags.setText(tunnel.extra_ssh_flags)
        self._connect_on_startup.setChecked(tunnel.connect_on_startup)
        for rule in tunnel.forward_rules:
            self._add_rule_row(rule)

    def get_config(self) -> TunnelConfig:
        """Return a TunnelConfig from the current form values."""
        return TunnelConfig(
            id=self._tunnel.id if self._tunnel else str(uuid.uuid4()),
            name=self._name.text().strip(),
            host=self._host.text().strip(),
            user=self._user.text().strip(),
            port=self._port.value(),
            forward_rules=[row.get_rule() for row in self._rule_rows],
            extra_ssh_flags=self._extra_flags.text().strip(),
            connect_on_startup=self._connect_on_startup.isChecked(),
        )

    def run(self) -> bool:
        """Show the dialog modally and return True if accepted."""
        return self.exec_() == QDialog.DialogCode.Accepted
