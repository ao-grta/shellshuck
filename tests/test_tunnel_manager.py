"""Tests for SSH tunnel manager — command construction, error parsing, and reconnect lifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shellshuck.managers.tunnel import (
    BACKOFF_FACTOR,
    INITIAL_RETRY_DELAY_MS,
    MAX_RETRIES,
    MAX_RETRY_DELAY_MS,
    TunnelManager,
    TunnelProcess,
    TunnelState,
    build_ssh_command,
    parse_ssh_error,
)
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


def test_build_command_with_identity_file() -> None:
    config = TunnelConfig(
        name="test",
        host="example.com",
        user="alice",
        identity_file="/home/alice/.config/shellshuck/keys/test_ed25519",
        forward_rules=[ForwardRule(8080, "localhost", 80)],
    )
    cmd = build_ssh_command(config)
    assert "-i" in cmd
    idx = cmd.index("-i")
    assert cmd[idx + 1] == "/home/alice/.config/shellshuck/keys/test_ed25519"
    # -i should appear before user@host
    assert idx < cmd.index("alice@example.com")


def test_build_command_without_identity_file() -> None:
    config = TunnelConfig(
        name="test",
        host="example.com",
        user="alice",
        forward_rules=[ForwardRule(8080, "localhost", 80)],
    )
    cmd = build_ssh_command(config)
    assert "-i" not in cmd


# ---------------------------------------------------------------------------
# Backoff delay math
# ---------------------------------------------------------------------------


class TestTunnelBackoffDelay:
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


def _make_tunnel_config() -> TunnelConfig:
    return TunnelConfig(
        name="test-tunnel",
        host="example.com",
        user="alice",
        forward_rules=[ForwardRule(8080, "localhost", 80)],
    )


@pytest.fixture()
def _patch_qt() -> object:  # noqa: PT005
    """Patch QProcess and QTimer so no real processes or timers are created."""
    with (
        patch("shellshuck.managers.tunnel.QProcess", autospec=True) as mock_qprocess_cls,
        patch("shellshuck.managers.tunnel.QTimer", autospec=True) as mock_qtimer_cls,
        patch("shellshuck.managers.tunnel.QProcessEnvironment", autospec=True),
    ):
        # QProcess instances returned by the constructor
        mock_proc = MagicMock()
        mock_proc.state.return_value = MagicMock()  # ProcessState.NotRunning
        mock_qprocess_cls.return_value = mock_proc
        mock_qprocess_cls.ProcessState = MagicMock()

        # QTimer instances returned by the constructor
        mock_timer = MagicMock()
        mock_qtimer_cls.return_value = mock_timer

        yield {
            "process_cls": mock_qprocess_cls,
            "process": mock_proc,
            "timer_cls": mock_qtimer_cls,
            "timer": mock_timer,
        }


class TestTunnelReconnectLifecycle:
    """Integration-style tests for the reconnect flow with patched Qt."""

    def test_unexpected_exit_triggers_reconnect(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = TunnelManager()
        config = _make_tunnel_config()
        tp = TunnelProcess(config=config, state=TunnelState.CONNECTED)
        tp.stderr_buffer = "Connection reset by peer\n"
        mgr._tunnels[config.id] = tp

        mgr._on_finished(tp, 255, MagicMock())

        assert tp.state == TunnelState.RECONNECTING
        assert tp.retry_count == 1

    def test_intentional_stop_prevents_reconnect(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = TunnelManager()
        config = _make_tunnel_config()
        tp = TunnelProcess(
            config=config,
            state=TunnelState.CONNECTED,
            intentional_stop=True,
        )
        tp.stderr_buffer = ""
        mgr._tunnels[config.id] = tp

        mgr._on_finished(tp, 0, MagicMock())

        assert tp.state == TunnelState.DISCONNECTED
        assert tp.retry_count == 0

    def test_max_retries_triggers_error(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = TunnelManager()
        config = _make_tunnel_config()
        tp = TunnelProcess(config=config, state=TunnelState.RECONNECTING)
        tp.retry_count = MAX_RETRIES  # already at limit
        mgr._tunnels[config.id] = tp

        mgr._schedule_reconnect(tp)

        assert tp.state == TunnelState.ERROR
        # retry_count should not have been incremented further
        assert tp.retry_count == MAX_RETRIES

    def test_retry_count_resets_on_success(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = TunnelManager()
        config = _make_tunnel_config()
        tp = TunnelProcess(config=config, state=TunnelState.RECONNECTING)
        tp.retry_count = 5
        mgr._tunnels[config.id] = tp

        mgr._on_started(tp)

        assert tp.retry_count == 0
        assert tp.state == TunnelState.CONNECTED

    def test_do_reconnect_launches_tunnel(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = TunnelManager()
        config = _make_tunnel_config()
        tp = TunnelProcess(config=config, state=TunnelState.RECONNECTING)
        tp.retry_timer = MagicMock()
        mgr._tunnels[config.id] = tp

        mgr._do_reconnect(tp)

        assert tp.retry_timer is None
        assert tp.state == TunnelState.CONNECTING
        # _launch should have created a new process via QProcess()
        _patch_qt["process_cls"].assert_called()

    def test_schedule_reconnect_creates_timer(
        self, qapp: object, _patch_qt: dict[str, MagicMock]
    ) -> None:
        mgr = TunnelManager()
        config = _make_tunnel_config()
        tp = TunnelProcess(config=config, state=TunnelState.CONNECTED)
        tp.retry_count = 0
        mgr._tunnels[config.id] = tp

        mgr._schedule_reconnect(tp)

        assert tp.retry_timer is not None
        _patch_qt["timer"].setSingleShot.assert_called_with(True)
        _patch_qt["timer"].start.assert_called_with(INITIAL_RETRY_DELAY_MS)
