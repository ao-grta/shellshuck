"""Tests for data models and their serialization."""

from shellshuck.models import AppConfig, ForwardRule, MountConfig, TunnelConfig


def test_forward_rule_to_ssh_arg() -> None:
    rule = ForwardRule(local_port=8080, remote_host="localhost", remote_port=80)
    assert rule.to_ssh_arg() == "8080:localhost:80"


def test_forward_rule_round_trip() -> None:
    rule = ForwardRule(local_port=5432, remote_host="db.internal", remote_port=5432)
    restored = ForwardRule.from_dict(rule.to_dict())
    assert restored == rule


def test_tunnel_config_round_trip() -> None:
    tunnel = TunnelConfig(
        name="prod-db",
        host="bastion.example.com",
        user="deploy",
        port=2222,
        forward_rules=[
            ForwardRule(local_port=5432, remote_host="db.internal", remote_port=5432),
            ForwardRule(local_port=6379, remote_host="redis.internal", remote_port=6379),
        ],
        extra_ssh_flags="-o StrictHostKeyChecking=no",
        connect_on_startup=True,
    )
    restored = TunnelConfig.from_dict(tunnel.to_dict())
    assert restored.id == tunnel.id
    assert restored.name == tunnel.name
    assert restored.host == tunnel.host
    assert restored.user == tunnel.user
    assert restored.port == tunnel.port
    assert len(restored.forward_rules) == 2
    assert restored.forward_rules[0].to_ssh_arg() == "5432:db.internal:5432"
    assert restored.extra_ssh_flags == tunnel.extra_ssh_flags
    assert restored.connect_on_startup is True


def test_tunnel_config_defaults() -> None:
    tunnel = TunnelConfig(name="test", host="example.com", user="user")
    assert tunnel.port == 22
    assert tunnel.forward_rules == []
    assert tunnel.extra_ssh_flags == ""
    assert tunnel.connect_on_startup is False
    assert tunnel.id  # auto-generated UUID


def test_mount_config_round_trip() -> None:
    mount = MountConfig(
        name="home-share",
        host="nas.local",
        user="alice",
        remote_path="/home/alice",
        local_mount="/mnt/nas",
        port=22,
        sshfs_flags="-o reconnect",
        connect_on_startup=True,
    )
    restored = MountConfig.from_dict(mount.to_dict())
    assert restored.id == mount.id
    assert restored.name == mount.name
    assert restored.host == mount.host
    assert restored.user == mount.user
    assert restored.remote_path == mount.remote_path
    assert restored.local_mount == mount.local_mount
    assert restored.sshfs_flags == mount.sshfs_flags
    assert restored.connect_on_startup is True


def test_mount_config_defaults() -> None:
    mount = MountConfig(
        name="test",
        host="example.com",
        user="user",
        remote_path="/data",
        local_mount="/mnt/data",
    )
    assert mount.port == 22
    assert mount.sshfs_flags == ""
    assert mount.connect_on_startup is False


def test_app_config_round_trip() -> None:
    config = AppConfig(
        tunnels=[
            TunnelConfig(
                name="t1",
                host="h1",
                user="u1",
                forward_rules=[ForwardRule(8080, "localhost", 80)],
            ),
        ],
        mounts=[
            MountConfig(
                name="m1",
                host="h2",
                user="u2",
                remote_path="/data",
                local_mount="/mnt/data",
            ),
        ],
        show_splash=False,
    )
    restored = AppConfig.from_dict(config.to_dict())
    assert len(restored.tunnels) == 1
    assert len(restored.mounts) == 1
    assert restored.tunnels[0].name == "t1"
    assert restored.mounts[0].name == "m1"
    assert restored.show_splash is False


def test_app_config_empty() -> None:
    config = AppConfig()
    restored = AppConfig.from_dict(config.to_dict())
    assert restored.tunnels == []
    assert restored.mounts == []
    assert restored.show_splash is True


def test_app_config_show_splash_default() -> None:
    """show_splash defaults to True when missing from persisted data."""
    restored = AppConfig.from_dict({"tunnels": [], "mounts": []})
    assert restored.show_splash is True
