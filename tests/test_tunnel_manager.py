"""Tests for SSH tunnel manager — command construction and error parsing."""

from shellshuck.managers.tunnel import build_ssh_command, parse_ssh_error
from shellshuck.models import ForwardRule, TunnelConfig


def test_build_basic_command() -> None:
    config = TunnelConfig(
        name="test",
        host="example.com",
        user="alice",
        forward_rules=[ForwardRule(8080, "localhost", 80)],
    )
    cmd = build_ssh_command(config)
    assert cmd[0] == "ssh"
    assert "-N" in cmd
    assert "-L" in cmd
    idx = cmd.index("-L")
    assert cmd[idx + 1] == "8080:localhost:80"
    assert cmd[-1] == "alice@example.com"


def test_build_command_custom_port() -> None:
    config = TunnelConfig(
        name="test",
        host="example.com",
        user="bob",
        port=2222,
        forward_rules=[ForwardRule(5432, "db.internal", 5432)],
    )
    cmd = build_ssh_command(config)
    idx = cmd.index("-p")
    assert cmd[idx + 1] == "2222"


def test_build_command_multiple_forwards() -> None:
    config = TunnelConfig(
        name="multi",
        host="bastion",
        user="deploy",
        forward_rules=[
            ForwardRule(5432, "db.internal", 5432),
            ForwardRule(6379, "redis.internal", 6379),
            ForwardRule(8080, "web.internal", 80),
        ],
    )
    cmd = build_ssh_command(config)
    l_indices = [i for i, arg in enumerate(cmd) if arg == "-L"]
    assert len(l_indices) == 3
    forwards = [cmd[i + 1] for i in l_indices]
    assert "5432:db.internal:5432" in forwards
    assert "6379:redis.internal:6379" in forwards
    assert "8080:web.internal:80" in forwards


def test_build_command_extra_flags() -> None:
    config = TunnelConfig(
        name="test",
        host="example.com",
        user="alice",
        extra_ssh_flags="-o StrictHostKeyChecking=no -v",
    )
    cmd = build_ssh_command(config)
    assert "-o" in cmd
    assert "StrictHostKeyChecking=no" in cmd
    assert "-v" in cmd


def test_build_command_no_forwards() -> None:
    config = TunnelConfig(name="test", host="example.com", user="alice")
    cmd = build_ssh_command(config)
    assert "-L" not in cmd


def test_parse_error_port_in_use() -> None:
    msg = parse_ssh_error("bind: Address already in use\nchannel_setup_fwd_listener")
    assert "port already in use" in msg.lower()


def test_parse_error_permission_denied() -> None:
    msg = parse_ssh_error("alice@example.com: Permission denied (publickey).")
    assert "permission denied" in msg.lower()


def test_parse_error_host_key() -> None:
    msg = parse_ssh_error("@@@@@@@@@@@@@@@\nHost key verification failed.\n")
    assert "host key" in msg.lower()


def test_parse_error_connection_refused() -> None:
    msg = parse_ssh_error("ssh: connect to host example.com port 22: Connection refused")
    assert "connection refused" in msg.lower()


def test_parse_error_timeout() -> None:
    msg = parse_ssh_error("ssh: connect to host example.com: Connection timed out")
    assert "timed out" in msg.lower()


def test_parse_error_unknown() -> None:
    msg = parse_ssh_error("some weird error nobody expected\n")
    assert msg == "some weird error nobody expected"


def test_parse_error_empty() -> None:
    msg = parse_ssh_error("")
    assert msg == "Unknown SSH error"
