"""SSH key generation and deployment."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment

logger = logging.getLogger(__name__)

ASKPASS_SCRIPT = str(Path(__file__).parent / "askpass.py")


def sanitize_name(name: str) -> str:
    """Convert a connection name to a safe filename component."""
    return re.sub(r"[^a-zA-Z0-9]", "_", name).strip("_") or "key"


def generate_key(name: str, keys_dir: Path) -> Path:
    """Generate an Ed25519 keypair and return the private key path.

    Creates keys_dir with mode 700 if it doesn't exist.
    Runs ssh-keygen synchronously (it's instant with empty passphrase).
    """
    keys_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(keys_dir, 0o700)

    safe_name = sanitize_name(name)
    key_path = keys_dir / f"{safe_name}_ed25519"

    # Remove existing key files to allow regeneration
    for suffix in ("", ".pub"):
        path = Path(str(key_path) + suffix)
        if path.exists():
            path.unlink()

    result = subprocess.run(
        [
            "ssh-keygen",
            "-t", "ed25519",
            "-N", "",
            "-f", str(key_path),
            "-C", f"shellshuck:{name}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ssh-keygen failed: {result.stderr.strip()}")

    logger.info("Generated SSH key: %s", key_path)
    return key_path


def deploy_key(
    pub_path: Path,
    host: str,
    user: str,
    port: int,
    parent: object | None = None,
) -> QProcess:
    """Deploy a public key via ssh-copy-id.

    Returns a QProcess so the caller can connect finished/error signals.
    Uses SSH_ASKPASS so the user enters their password once in a GUI dialog.
    """
    process = QProcess(parent)  # type: ignore[arg-type]

    env = QProcessEnvironment.systemEnvironment()
    env.insert("SSH_ASKPASS", ASKPASS_SCRIPT)
    env.insert("SSH_ASKPASS_REQUIRE", "force")
    process.setProcessEnvironment(env)

    process.setProgram("ssh-copy-id")
    process.setArguments([
        "-i", str(pub_path),
        "-p", str(port),
        "-o", "StrictHostKeyChecking=accept-new",
        f"{user}@{host}",
    ])

    return process
