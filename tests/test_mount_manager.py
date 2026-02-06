"""Tests for SSHFS mount manager — command construction."""

from shellshuck.managers.mount import build_sshfs_command
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
