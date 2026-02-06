"""Tests for config persistence."""

from pathlib import Path

from shellshuck.config import ConfigManager
from shellshuck.models import AppConfig, ForwardRule, MountConfig, TunnelConfig


def test_save_and_load(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_path)

    config = AppConfig(
        tunnels=[
            TunnelConfig(
                name="dev-tunnel",
                host="dev.example.com",
                user="dev",
                forward_rules=[ForwardRule(3000, "localhost", 3000)],
            )
        ],
        mounts=[
            MountConfig(
                name="dev-mount",
                host="dev.example.com",
                user="dev",
                remote_path="/srv/app",
                local_mount="/mnt/dev",
            )
        ],
    )

    manager.save(config)
    assert config_path.exists()

    loaded = manager.load()
    assert len(loaded.tunnels) == 1
    assert len(loaded.mounts) == 1
    assert loaded.tunnels[0].name == "dev-tunnel"
    assert loaded.tunnels[0].forward_rules[0].local_port == 3000
    assert loaded.mounts[0].name == "dev-mount"
    assert loaded.mounts[0].remote_path == "/srv/app"


def test_load_missing_file(tmp_path: Path) -> None:
    config_path = tmp_path / "nonexistent" / "config.json"
    manager = ConfigManager(config_path=config_path)
    config = manager.load()
    assert config.tunnels == []
    assert config.mounts == []


def test_save_creates_directories(tmp_path: Path) -> None:
    config_path = tmp_path / "nested" / "dir" / "config.json"
    manager = ConfigManager(config_path=config_path)
    manager.save(AppConfig())
    assert config_path.exists()


def test_ids_preserved_across_save_load(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_path)

    tunnel = TunnelConfig(name="t", host="h", user="u")
    mount = MountConfig(name="m", host="h", user="u", remote_path="/a", local_mount="/b")

    config = AppConfig(tunnels=[tunnel], mounts=[mount])
    manager.save(config)

    loaded = manager.load()
    assert loaded.tunnels[0].id == tunnel.id
    assert loaded.mounts[0].id == mount.id
