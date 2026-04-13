"""Entry point for the photobooth application.

Usage:
    python -m photobooth
    photobooth              (if installed via pip)
"""

import signal
import sys
from pathlib import Path

from photobooth.config import load_config
from photobooth.app import PhotoboothApp


def main() -> None:
    """Bootstrap the application: load config, then launch the Kivy app."""
    config_path = Path("booth.toml")
    if not config_path.exists():
        print(f"Warning: config file '{config_path}' not found, using defaults.")
        config_path = None

    config = load_config(config_path)
    app = PhotoboothApp(config=config)

    # Handle Ctrl+C gracefully — trigger Kivy's clean shutdown
    def _handle_sigint(sig, frame):
        print()  # Newline after ^C
        app.stop()

    signal.signal(signal.SIGINT, _handle_sigint)

    app.run()


if __name__ == "__main__":
    main()
