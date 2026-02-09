"""SSHFS mount lifecycle management via QProcess."""

from __future__ import annotations

import logging
import shlex
from enum import Enum, auto

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from shellshuck.models import MountConfig
from shellshuck.resources import get_askpass_path

logger = logging.getLogger(__name__)

ASKPASS_SCRIPT = get_askpass_path()

HEALTH_CHECK_INTERVAL_MS = 30000
INITIAL_RETRY_DELAY_MS = 2000
MAX_RETRY_DELAY_MS = 60000
BACKOFF_FACTOR = 2
MAX_RETRIES = 10


class MountState(Enum):
    UNMOUNTED = auto()
    MOUNTING = auto()
    MOUNTED = auto()
    UNHEALTHY = auto()
    UNMOUNTING = auto()
    RECONNECTING = auto()
    ERROR = auto()


class MountProcess:
    """Tracks state for a single SSHFS mount."""

    def __init__(self, config: MountConfig) -> None:
        self.config = config
        self.process: QProcess | None = None
        self.state = MountState.UNMOUNTED
        self.retry_count: int = 0
        self.retry_timer: QTimer | None = None
        self.health_timer: QTimer | None = None
        self.intentional_stop: bool = False
        self.stderr_buffer: str = ""


def build_sshfs_command(config: MountConfig) -> list[str]:
    """Build the sshfs command for a mount config."""
    cmd = [
        "sshfs",
        "-o",
        "reconnect",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"port={config.port}",
        "-f",  # foreground — so QProcess can track it
    ]

    if config.identity_file:
        cmd.extend(["-o", f"IdentityFile={config.identity_file}"])

    if config.sshfs_flags:
        cmd.extend(shlex.split(config.sshfs_flags))

    cmd.append(f"{config.user}@{config.host}:{config.remote_path}")
    cmd.append(config.local_mount)
    return cmd


class MountManager(QObject):
    """Manages SSHFS mount processes."""

    mount_state_changed = Signal(str, MountState)  # config_id, new_state
    mount_error = Signal(str, str)  # config_id, error_msg
    mount_log = Signal(str, str)  # config_id, log_message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mounts: dict[str, MountProcess] = {}

    @property
    def mounts(self) -> dict[str, MountProcess]:
        return self._mounts

    def mount(self, config: MountConfig) -> None:
        """Start an SSHFS mount."""
        if config.id in self._mounts:
            existing = self._mounts[config.id]
            if existing.state in (MountState.MOUNTED, MountState.MOUNTING):
                logger.warning("Mount %s already active", config.name)
                return

        mp = MountProcess(config)
        mp.state = MountState.MOUNTING
        self._mounts[config.id] = mp
        self._launch(mp)

    def unmount(self, config_id: str) -> None:
        """Unmount an SSHFS mount."""
        mp = self._mounts.get(config_id)
        if mp is None:
            return

        mp.intentional_stop = True

        if mp.retry_timer is not None:
            mp.retry_timer.stop()
            mp.retry_timer = None

        if mp.health_timer is not None:
            mp.health_timer.stop()
            mp.health_timer = None

        self._set_state(mp, MountState.UNMOUNTING)
        self.mount_log.emit(config_id, f"Unmounting '{mp.config.name}'")

        # Try graceful fusermount -u first
        self._run_fusermount(mp, lazy=False)

    def unmount_all(self) -> None:
        """Unmount all active mounts."""
        for config_id in list(self._mounts.keys()):
            self.unmount(config_id)

    def get_state(self, config_id: str) -> MountState:
        mp = self._mounts.get(config_id)
        return mp.state if mp else MountState.UNMOUNTED

    def _launch(self, mp: MountProcess) -> None:
        """Launch the sshfs process."""
        cmd = build_sshfs_command(mp.config)
        logger.info("Mounting '%s': %s", mp.config.name, " ".join(cmd))
        self.mount_log.emit(mp.config.id, f"Mounting: {' '.join(cmd)}")
        self._set_state(mp, MountState.MOUNTING)
        mp.intentional_stop = False
        mp.stderr_buffer = ""

        process = QProcess(self)
        mp.process = process

        # Set SSH_ASKPASS so password/passphrase prompts show a GUI dialog
        env = QProcessEnvironment.systemEnvironment()
        env.insert("SSH_ASKPASS", ASKPASS_SCRIPT)
        env.insert("SSH_ASKPASS_REQUIRE", "force")
        process.setProcessEnvironment(env)

        process.setProgram(cmd[0])
        process.setArguments(cmd[1:])

        process.readyReadStandardError.connect(lambda: self._on_stderr(mp))
        process.started.connect(lambda: self._on_started(mp))
        process.finished.connect(lambda code, status: self._on_finished(mp, code, status))

        process.start()

    def _on_started(self, mp: MountProcess) -> None:
        """Called when sshfs process starts."""
        self._set_state(mp, MountState.MOUNTED)
        mp.retry_count = 0
        self.mount_log.emit(mp.config.id, f"Mount '{mp.config.name}' active")

        # Start health check timer
        self._start_health_check(mp)

    def _on_stderr(self, mp: MountProcess) -> None:
        """Accumulate stderr output."""
        if mp.process is None:
            return
        data = mp.process.readAllStandardError().data().decode(errors="replace")
        mp.stderr_buffer += data
        # Log each complete line
        while "\n" in mp.stderr_buffer:
            line, mp.stderr_buffer = mp.stderr_buffer.split("\n", 1)
            line = line.strip()
            if line:
                self.mount_log.emit(mp.config.id, f"[sshfs] {line}")

    def _on_finished(
        self, mp: MountProcess, exit_code: int, exit_status: QProcess.ExitStatus
    ) -> None:
        """Handle sshfs process exit."""
        if mp.health_timer is not None:
            mp.health_timer.stop()
            mp.health_timer = None

        if mp.intentional_stop:
            self._set_state(mp, MountState.UNMOUNTED)
            self.mount_log.emit(mp.config.id, f"Mount '{mp.config.name}' stopped")
            return

        error_msg = f"sshfs exited with code {exit_code}"
        self.mount_error.emit(mp.config.id, error_msg)
        self.mount_log.emit(mp.config.id, f"Mount '{mp.config.name}' failed: {error_msg}")

        self._schedule_reconnect(mp)

    def _run_fusermount(self, mp: MountProcess, lazy: bool = False) -> None:
        """Run fusermount to unmount."""
        args = ["-uz" if lazy else "-u", mp.config.local_mount]
        process = QProcess(self)
        process.setProgram("fusermount")
        process.setArguments(args)
        process.finished.connect(lambda code, status: self._on_fusermount_finished(mp, code, lazy))
        process.start()

    def _on_fusermount_finished(self, mp: MountProcess, exit_code: int, was_lazy: bool) -> None:
        """Handle fusermount result."""
        if exit_code == 0:
            self._set_state(mp, MountState.UNMOUNTED)
            self.mount_log.emit(mp.config.id, f"Unmounted '{mp.config.name}' cleanly")
        elif not was_lazy:
            # Graceful failed, try lazy
            self.mount_log.emit(mp.config.id, "Graceful unmount failed, trying lazy unmount")
            self._run_fusermount(mp, lazy=True)
        else:
            self._set_state(mp, MountState.ERROR)
            self.mount_error.emit(mp.config.id, "Failed to unmount (even with lazy)")
            self.mount_log.emit(mp.config.id, f"Failed to unmount '{mp.config.name}'")

    def _start_health_check(self, mp: MountProcess) -> None:
        """Start periodic health checks using mountpoint -q."""
        if mp.health_timer is not None:
            mp.health_timer.stop()

        timer = QTimer(self)
        timer.timeout.connect(lambda: self._check_health(mp))
        timer.start(HEALTH_CHECK_INTERVAL_MS)
        mp.health_timer = timer

    def _check_health(self, mp: MountProcess) -> None:
        """Run mountpoint -q to verify the mount is still alive."""
        if mp.state not in (MountState.MOUNTED, MountState.UNHEALTHY):
            return

        process = QProcess(self)
        process.setProgram("mountpoint")
        process.setArguments(["-q", mp.config.local_mount])
        process.finished.connect(lambda code, status: self._on_health_check_finished(mp, code))
        process.start()

    def _on_health_check_finished(self, mp: MountProcess, exit_code: int) -> None:
        """Handle health check result."""
        if exit_code == 0:
            if mp.state == MountState.UNHEALTHY:
                self._set_state(mp, MountState.MOUNTED)
                self.mount_log.emit(mp.config.id, f"Mount '{mp.config.name}' recovered")
        else:
            self._set_state(mp, MountState.UNHEALTHY)
            self.mount_log.emit(mp.config.id, f"Mount '{mp.config.name}' unhealthy")
            self.mount_error.emit(mp.config.id, "Mount point not responding")

    def _schedule_reconnect(self, mp: MountProcess) -> None:
        """Schedule reconnection with exponential backoff."""
        if mp.retry_count >= MAX_RETRIES:
            self._set_state(mp, MountState.ERROR)
            self.mount_error.emit(
                mp.config.id,
                f"Mount '{mp.config.name}' failed after {MAX_RETRIES} attempts",
            )
            self.mount_log.emit(
                mp.config.id,
                f"Giving up on '{mp.config.name}' after {MAX_RETRIES} attempts",
            )
            return

        delay = min(
            INITIAL_RETRY_DELAY_MS * (BACKOFF_FACTOR**mp.retry_count),
            MAX_RETRY_DELAY_MS,
        )
        mp.retry_count += 1
        self._set_state(mp, MountState.RECONNECTING)
        self.mount_log.emit(
            mp.config.id,
            f"Reconnecting '{mp.config.name}' in {delay / 1000:.0f}s (attempt {mp.retry_count})",
        )

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._do_reconnect(mp))
        timer.start(int(delay))
        mp.retry_timer = timer

    def _do_reconnect(self, mp: MountProcess) -> None:
        """Perform a reconnection attempt."""
        mp.retry_timer = None
        self._launch(mp)

    def _set_state(self, mp: MountProcess, state: MountState) -> None:
        mp.state = state
        self.mount_state_changed.emit(mp.config.id, state)
