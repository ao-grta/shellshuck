<p align="center">
  <img src="resources/icons/shellshuck.svg" width="128" alt="Shellshuck logo">
</p>

<h1 align="center">Shellshuck</h1>

<p align="center">
  A desktop GUI for managing SSH tunnels and SSHFS mounts on Linux.
</p>

---

## Features

- **SSH Tunnels** — configure and manage `ssh -L` port forwards with multiple rules per tunnel
- **SSHFS Mounts** — mount remote directories locally via SSHFS with health checks
- **System Tray** — runs in the background; tray icon reflects connection health (green/red/grey)
- **Auto-Reconnect** — exponential backoff reconnect on tunnel or mount failures
- **SSH Askpass** — built-in `SSH_ASKPASS` support for passphrase prompts
- **Connect on Startup** — optionally auto-connect tunnels and mounts when the app launches
- **Desktop Notifications** — get notified on connection errors

## Requirements

- Python 3.10+
- PySide6 (Qt 6)
- System binaries: `ssh`, `sshfs`, `fusermount`

## Install & Run

```bash
# Clone the repo
git clone https://github.com/your-user/shellshuck.git
cd shellshuck

# Install with uv
uv pip install -e ".[dev]"

# Run
uv run python -m shellshuck
```

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Format check
uv run ruff format --check src/ tests/

# Type check
uv run mypy src/shellshuck/
```

## Configuration

Config is stored at `~/.config/shellshuck/config.json`. No secrets are stored — authentication relies on your SSH agent and key-based auth.

## License

[MIT](LICENSE)
