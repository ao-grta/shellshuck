"""SSH tunnel lifecycle management via QProcess."""

from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from shellshuck.models import TunnelConfig

logger = logging.getLogger(__name__)

# Known SSH error patterns and their human-readable messages
SSH_ERROR_PATTERNS: list[tuple[str, str]] = [
    ("Address already in use", "Local port already in use"),
    ("Permission denied", "Authentication failed (permission denied)"),
    ("Host key verification failed", "Host key verification failed — check known_hosts"),
    ("Connection refused", "Connection refused by remote host"),
    ("Connection timed out", "Connection timed out"),
    ("Network is unreachable", "Network is unreachable"),
    ("No route to host", "No route to host"),
    ("Could not resolve hostname", "Could not resolve hostname"),
    ("Connection reset by peer", "Connection reset by remote host"),
    ("broken pipe", "Connection lost (broken pipe)"),
]

# Reconnect backoff settings
ASKPASS_SCRIPT = str(Path(__file__).parent.parent / "askpass.py")

INITIAL_RETRY_DELAY_MS = 2000
MAX_RETRY_DELAY_MS = 60000
BACKOFF_FACTOR = 2


class TunnelState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()


@dataclass
class TunnelProcess:
    """Tracks a running tunnel's process and reconnect state."""

    config: TunnelConfig
    process: QProcess | None = None
    retry_count: int = 0
    retry_timer: QTimer | None = None
    state: TunnelState = TunnelState.DISCONNECTED
    stderr_buffer: str = ""
    intentional_stop: bool = False


def parse_ssh_error(stderr: str) -> str:
    """Extract a human-readable error from SSH stderr output."""
    stderr_lower = stderr.lower()
    for pattern, message in SSH_ERROR_PATTERNS:
        if pattern.lower() in stderr_lower:
            return message
    # Return the last non-empty line as fallback
    lines = [line.strip() for line in stderr.strip().splitlines() if line.strip()]
    return lines[-1] if lines else "Unknown SSH error"


def build_ssh_command(config: TunnelConfig) -> list[str]:
    """Build the ssh command line for a tunnel config."""
    cmd = [
        "ssh",
        "-N",  # no remote command
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(config.port),
    ]

    for rule in config.forward_rules:
        cmd.extend(["-L", rule.to_ssh_arg()])

    if config.identity_file:
        cmd.extend(["-i", config.identity_file])

    if config.extra_ssh_flags:
        cmd.extend(shlex.split(config.extra_ssh_flags))

    cmd.append(f"{config.user}@{config.host}")
    return cmd


class TunnelManager(QObject):
    """Manages SSH tunnel processes."""

    tunnel_state_changed = Signal(str, TunnelState)  # config_id, new_state
    tunnel_error = Signal(str, str)  # config_id, error_msg
    tunnel_log = Signal(str, str)  # config_id, log_message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tunnels: dict[str, TunnelProcess] = {}

    @property
    def tunnels(self) -> dict[str, TunnelProcess]:
        return self._tunnels

    def start(self, config: TunnelConfig) -> None:
        """Start an SSH tunnel for the given config."""
        if config.id in self._tunnels:
            existing = self._tunnels[config.id]
            if existing.state in (TunnelState.CONNECTED, TunnelState.CONNECTING):
                logger.warning("Tunnel %s already running", config.name)
                return

        tp = TunnelProcess(config=config, state=TunnelState.CONNECTING)
        self._tunnels[config.id] = tp
        self._launch(tp)

    def stop(self, config_id: str) -> None:
        """Stop a running tunnel."""
        tp = self._tunnels.get(config_id)
        if tp is None:
            return

        tp.intentional_stop = True

        if tp.retry_timer is not None:
            tp.retry_timer.stop()
            tp.retry_timer = None

        if tp.process is not None and tp.process.state() != QProcess.ProcessState.NotRunning:
            tp.process.terminate()
            if not tp.process.waitForFinished(3000):
                tp.process.kill()

        self._set_state(tp, TunnelState.DISCONNECTED)
        self.tunnel_log.emit(config_id, f"Tunnel '{tp.config.name}' stopped")

    def stop_all(self) -> None:
        """Stop all running tunnels."""
        for config_id in list(self._tunnels.keys()):
            self.stop(config_id)

    def get_state(self, config_id: str) -> TunnelState:
        tp = self._tunnels.get(config_id)
        return tp.state if tp else TunnelState.DISCONNECTED

    def _launch(self, tp: TunnelProcess) -> None:
        """Launch the SSH process for a tunnel."""
        cmd = build_ssh_command(tp.config)
        logger.info("Starting tunnel '%s': %s", tp.config.name, " ".join(cmd))
        self.tunnel_log.emit(tp.config.id, f"Starting tunnel: {' '.join(cmd)}")

        process = QProcess(self)
        tp.process = process
        tp.stderr_buffer = ""
        tp.intentional_stop = False

        # Set SSH_ASKPASS so password/passphrase prompts show a GUI dialog
        env = QProcessEnvironment.systemEnvironment()
        env.insert("SSH_ASKPASS", ASKPASS_SCRIPT)
        env.insert("SSH_ASKPASS_REQUIRE", "force")
        process.setProcessEnvironment(env)

        process.setProgram(cmd[0])
        process.setArguments(cmd[1:])

        process.readyReadStandardError.connect(lambda: self._on_stderr(tp))
        process.started.connect(lambda: self._on_started(tp))
        process.finished.connect(lambda code, status: self._on_finished(tp, code, status))

        process.start()

    def _on_started(self, tp: TunnelProcess) -> None:
        """Called when the SSH process starts."""
        self._set_state(tp, TunnelState.CONNECTED)
        tp.retry_count = 0
        self.tunnel_log.emit(tp.config.id, f"Tunnel '{tp.config.name}' connected")

    def _on_stderr(self, tp: TunnelProcess) -> None:
        """Accumulate stderr output."""
        if tp.process is None:
            return
        data = tp.process.readAllStandardError().data().decode(errors="replace")
        tp.stderr_buffer += data
        # Log each complete line
        while "\n" in tp.stderr_buffer:
            line, tp.stderr_buffer = tp.stderr_buffer.split("\n", 1)
            line = line.strip()
            if line:
                self.tunnel_log.emit(tp.config.id, f"[ssh] {line}")

    def _on_finished(
        self, tp: TunnelProcess, exit_code: int, exit_status: QProcess.ExitStatus
    ) -> None:
        """Handle process exit — reconnect on unexpected failures."""
        if tp.intentional_stop:
            self._set_state(tp, TunnelState.DISCONNECTED)
            return

        error_msg = parse_ssh_error(tp.stderr_buffer)
        self.tunnel_error.emit(tp.config.id, error_msg)
        self.tunnel_log.emit(
            tp.config.id,
            f"Tunnel '{tp.config.name}' exited (code={exit_code}): {error_msg}",
        )

        # Schedule reconnect with exponential backoff
        self._schedule_reconnect(tp)

    def _schedule_reconnect(self, tp: TunnelProcess) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        delay = min(
            INITIAL_RETRY_DELAY_MS * (BACKOFF_FACTOR**tp.retry_count),
            MAX_RETRY_DELAY_MS,
        )
        tp.retry_count += 1
        self._set_state(tp, TunnelState.RECONNECTING)
        self.tunnel_log.emit(
            tp.config.id,
            f"Reconnecting '{tp.config.name}' in {delay / 1000:.0f}s (attempt {tp.retry_count})",
        )

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._do_reconnect(tp))
        timer.start(int(delay))
        tp.retry_timer = timer

    def _do_reconnect(self, tp: TunnelProcess) -> None:
        """Perform a reconnection attempt."""
        tp.retry_timer = None
        self._set_state(tp, TunnelState.CONNECTING)
        self._launch(tp)

    def _set_state(self, tp: TunnelProcess, state: TunnelState) -> None:
        tp.state = state
        self.tunnel_state_changed.emit(tp.config.id, state)
