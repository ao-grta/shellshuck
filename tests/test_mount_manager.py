"""Tests for SSHFS mount manager — command construction and reconnect lifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shellshuck.managers.mount import (
    BACKOFF_FACTOR,
    INITIAL_RETRY_DELAY_MS,
    MAX_RETRIES,
    MAX_RETRY_DELAY_MS,
    MountManager,
    MountProcess,
    MountState,
    build_sshfs_command,
)
from shellshuck.models import MountConfig


def test_build_basic_mount_command() -> None:
    config = MountConfig(
        name="test",
        host="nas.local",
        user="alice",
        remote_path="/home/alice",
        local_mount="/mnt/nas",
    )
    cmd = build_sshfs_command(config)
    assert cmd[0] == "sshfs"
    assert "-f" in cmd  # foreground mode for QProcess
    assert "alice@nas.local:/home/alice" in cmd
    assert "/mnt/nas" in cmd


def test_build_mount_command_custom_port() -> None:
    config = MountConfig(
        name="test",
        host="nas.local",
        user="alice",
        remote_path="/data",
        local_mount="/mnt/data",
        port=2222,
    )
    cmd = build_sshfs_command(config)
    # Find port option
    found_port = False
    for i, arg in enumerate(cmd):
        if arg == "-o" and i + 1 < len(cmd) and cmd[i + 1] == "port=2222":
            found_port = True
    assert found_port, f"port=2222 not found in command: {cmd}"


def test_build_mount_command_extra_flags() -> None:
    config = MountConfig(
        name="test",
        host="nas.local",
        user="alice",
        remote_path="/data",
        local_mount="/mnt/data",
        sshfs_flags="-o allow_other -o IdentityFile=/home/alice/.ssh/id_ed25519",
    )
    cmd = build_sshfs_command(config)
    assert "allow_other" in cmd
    assert "IdentityFile=/home/alice/.ssh/id_ed25519" in cmd


def test_build_mount_command_has_reconnect() -> None:
    config = MountConfig(
        name="test",
        host="nas.local",
        user="alice",
        remote_path="/data",
        local_mount="/mnt/data",
    )
    cmd = build_sshfs_command(config)
    # Should have -o reconnect
    found = False
    for i, arg in enumerate(cmd):
        if arg == "-o" and i + 1 < len(cmd) and cmd[i + 1] == "reconnect":
            found = True
    assert found, f"reconnect option not found in: {cmd}"


def test_build_mount_command_has_keepalive() -> None:
    config = MountConfig(
        name="test",
        host="nas.local",
        user="alice",
        remote_path="/data",
        local_mount="/mnt/data",
    )
    cmd = build_sshfs_command(config)
    cmd_str = " ".join(cmd)
    assert "ServerAliveInterval" in cmd_str
    assert "ServerAliveCountMax" in cmd_str


def test_build_mount_command_with_identity_file() -> None:
    config = MountConfig(
        name="test",
        host="nas.local",
        user="alice",
        remote_path="/data",
        local_mount="/mnt/data",
        identity_file="/home/alice/.config/shellshuck/keys/test_ed25519",
    )
    cmd = build_sshfs_command(config)
    # Find the IdentityFile option
    found = False
    for i, arg in enumerate(cmd):
        if (
            arg == "-o"
            and i + 1 < len(cmd)
            and cmd[i + 1] == "IdentityFile=/home/alice/.config/shellshuck/keys/test_ed25519"
        ):
            found = True
    assert found, f"IdentityFile option not found in: {cmd}"


def test_build_mount_command_without_identity_file() -> None:
    config = MountConfig(
        name="test",
        host="nas.local",
        user="alice",
        remote_path="/data",
        local_mount="/mnt/data",
    )
    cmd = build_sshfs_command(config)
    cmd_str = " ".join(cmd)
    assert "IdentityFile" not in cmd_str


# ---------------------------------------------------------------------------
# Backoff delay math
# ---------------------------------------------------------------------------


class TestMountBackoffDelay:
    """Pure math tests for the exponential backoff formula."""

    def test_first_delay(self) -> None:
        delay = min(INITIAL_RETRY_DELAY_MS * (BACKOFF_FACTOR**0), MAX_RETRY_DELAY_MS)
        assert delay == INITIAL_RETRY_DELAY_MS

    def test_second_delay(self) -> None:
        delay = min(INITIAL_RETRY_DELAY_MS * (BACKOFF_FACTOR**1), MAX_RETRY_DELAY_MS)
        assert delay == INITIAL_RETRY_DELAY_MS * BACKOFF_FACTOR

    def test_delay_capped_at_max(self) -> None:
        huge_count = 100
        delay = min(
            INITIAL_RETRY_DELAY_MS * (BACKOFF_FACTOR**huge_count),
            MAX_RETRY_DELAY_MS,
        )
        assert delay == MAX_RETRY_DELAY_MS


# ---------------------------------------------------------------------------
# Reconnect lifecycle
# ---------------------------------------------------------------------------


def _make_mount_config() -> MountConfig:
    return MountConfig(
        name="test-mount",
        host="nas.local",
        user="alice",
        remote_path="/data",
        local_mount="/mnt/data",
    )


@pytest.fixture()
def _patch_qt() -> object:  # noqa: PT005
    """Patch QProcess and QTimer so no real processes or timers are created."""
    with (
        patch("shellshuck.managers.mount.QProcess", autospec=True) as mock_qprocess_cls,
        patch("shellshuck.managers.mount.QTimer", autospec=True) as mock_qtimer_cls,
        patch("shellshuck.managers.mount.QProcessEnvironment", autospec=True),
    ):
        mock_proc = MagicMock()
        mock_proc.state.return_value = MagicMock()
        mock_qprocess_cls.return_value = mock_proc
        mock_qprocess_cls.ProcessState = MagicMock()

        mock_timer = MagicMock()
        mock_qtimer_cls.return_value = mock_timer

        yield {
            "process_cls": mock_qprocess_cls,
            "process": mock_proc,
            "timer_cls": mock_qtimer_cls,
            "timer": mock_timer,
        }


class TestMountReconnectLifecycle:
    """Integration-style tests for the reconnect flow with patched Qt."""

    def test_unexpected_exit_triggers_reconnect(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = MountManager()
        config = _make_mount_config()
        mp = MountProcess(config)
        mp.state = MountState.MOUNTED
        mp.stderr_buffer = "connection lost\n"
        mgr._mounts[config.id] = mp

        mgr._on_finished(mp, 255, MagicMock())

        assert mp.state == MountState.RECONNECTING
        assert mp.retry_count == 1

    def test_intentional_stop_prevents_reconnect(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = MountManager()
        config = _make_mount_config()
        mp = MountProcess(config)
        mp.state = MountState.MOUNTED
        mp.intentional_stop = True
        mp.stderr_buffer = ""
        mgr._mounts[config.id] = mp

        mgr._on_finished(mp, 0, MagicMock())

        assert mp.state == MountState.UNMOUNTED
        assert mp.retry_count == 0

    def test_max_retries_triggers_error(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = MountManager()
        config = _make_mount_config()
        mp = MountProcess(config)
        mp.state = MountState.RECONNECTING
        mp.retry_count = MAX_RETRIES
        mgr._mounts[config.id] = mp

        mgr._schedule_reconnect(mp)

        assert mp.state == MountState.ERROR
        assert mp.retry_count == MAX_RETRIES

    def test_retry_count_resets_on_success(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = MountManager()
        config = _make_mount_config()
        mp = MountProcess(config)
        mp.state = MountState.RECONNECTING
        mp.retry_count = 5
        mgr._mounts[config.id] = mp

        mgr._on_started(mp)

        assert mp.retry_count == 0
        assert mp.state == MountState.MOUNTED

    def test_do_reconnect_launches_mount(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = MountManager()
        config = _make_mount_config()
        mp = MountProcess(config)
        mp.state = MountState.RECONNECTING
        mp.retry_timer = MagicMock()
        mgr._mounts[config.id] = mp

        mgr._do_reconnect(mp)

        assert mp.retry_timer is None
        assert mp.state == MountState.MOUNTING
        _patch_qt["process_cls"].assert_called()

    def test_schedule_reconnect_creates_timer(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = MountManager()
        config = _make_mount_config()
        mp = MountProcess(config)
        mp.state = MountState.MOUNTED
        mp.retry_count = 0
        mgr._mounts[config.id] = mp

        mgr._schedule_reconnect(mp)

        assert mp.retry_timer is not None
        _patch_qt["timer"].setSingleShot.assert_called_with(True)
        _patch_qt["timer"].start.assert_called_with(INITIAL_RETRY_DELAY_MS)
