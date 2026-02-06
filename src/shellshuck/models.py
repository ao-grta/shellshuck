"""Data models for tunnel and mount configurations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class ForwardRule:
    """A single SSH -L forwarding rule."""

    local_port: int
    remote_host: str
    remote_port: int

    def to_ssh_arg(self) -> str:
        return f"{self.local_port}:{self.remote_host}:{self.remote_port}"

    def to_dict(self) -> dict[str, int | str]:
        return {
            "local_port": self.local_port,
            "remote_host": self.remote_host,
            "remote_port": self.remote_port,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int | str]) -> ForwardRule:
        return cls(
            local_port=int(data["local_port"]),
            remote_host=str(data["remote_host"]),
            remote_port=int(data["remote_port"]),
        )


@dataclass
class TunnelConfig:
    """Configuration for an SSH tunnel."""

    name: str
    host: str
    user: str
    port: int = 22
    forward_rules: list[ForwardRule] = field(default_factory=list)
    extra_ssh_flags: str = ""
    connect_on_startup: bool = False
    identity_file: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "user": self.user,
            "port": self.port,
            "forward_rules": [r.to_dict() for r in self.forward_rules],
            "extra_ssh_flags": self.extra_ssh_flags,
            "connect_on_startup": self.connect_on_startup,
            "identity_file": self.identity_file,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TunnelConfig:
        rules_data = data.get("forward_rules", [])
        assert isinstance(rules_data, list)
        return cls(
            id=str(data.get("id", uuid.uuid4())),
            name=str(data["name"]),
            host=str(data["host"]),
            user=str(data["user"]),
            port=int(data.get("port", 22)),  # type: ignore[arg-type]
            forward_rules=[ForwardRule.from_dict(r) for r in rules_data],
            extra_ssh_flags=str(data.get("extra_ssh_flags", "")),
            connect_on_startup=bool(data.get("connect_on_startup", False)),
            identity_file=str(data.get("identity_file", "")),
        )


@dataclass
class MountConfig:
    """Configuration for an SSHFS mount."""

    name: str
    host: str
    user: str
    remote_path: str
    local_mount: str
    port: int = 22
    sshfs_flags: str = ""
    connect_on_startup: bool = False
    identity_file: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "user": self.user,
            "remote_path": self.remote_path,
            "local_mount": self.local_mount,
            "port": self.port,
            "sshfs_flags": self.sshfs_flags,
            "connect_on_startup": self.connect_on_startup,
            "identity_file": self.identity_file,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MountConfig:
        return cls(
            id=str(data.get("id", uuid.uuid4())),
            name=str(data["name"]),
            host=str(data["host"]),
            user=str(data["user"]),
            remote_path=str(data["remote_path"]),
            local_mount=str(data["local_mount"]),
            port=int(data.get("port", 22)),  # type: ignore[arg-type]
            sshfs_flags=str(data.get("sshfs_flags", "")),
            connect_on_startup=bool(data.get("connect_on_startup", False)),
            identity_file=str(data.get("identity_file", "")),
        )


@dataclass
class AppConfig:
    """Top-level application configuration."""

    tunnels: list[TunnelConfig] = field(default_factory=list)
    mounts: list[MountConfig] = field(default_factory=list)
    show_splash: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "tunnels": [t.to_dict() for t in self.tunnels],
            "mounts": [m.to_dict() for m in self.mounts],
            "show_splash": self.show_splash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AppConfig:
        tunnels_data = data.get("tunnels", [])
        mounts_data = data.get("mounts", [])
        assert isinstance(tunnels_data, list)
        assert isinstance(mounts_data, list)
        return cls(
            tunnels=[TunnelConfig.from_dict(t) for t in tunnels_data],
            mounts=[MountConfig.from_dict(m) for m in mounts_data],
            show_splash=bool(data.get("show_splash", True)),
        )
