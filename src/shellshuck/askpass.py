#!/usr/bin/env python3
"""SSH_ASKPASS helper — shows a Qt dialog for password/passphrase prompts."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit


def main() -> None:
    # SSH passes the prompt as the first argument (or via stdin context)
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Enter passphrase:"

    app = QApplication(sys.argv)
    app.setApplicationName("Shellshuck")

    text, ok = QInputDialog.getText(
        None,
        "Shellshuck — SSH Authentication",
        prompt,
        QLineEdit.EchoMode.Password,
    )

    if ok and text:
        print(text)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
