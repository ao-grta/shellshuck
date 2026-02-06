"""Entry point for shellshuck."""

import logging
import sys


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    from shellshuck.app import ShellshuckApp

    app = ShellshuckApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
