"""Shared constants."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Token lifetimes
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
OTP_EXPIRE_MINUTES = 5
OTP_CODE_LENGTH = 6

# WebSocket
HEARTBEAT_INTERVAL_SECONDS = 10
HEARTBEAT_TIMEOUT_SECONDS = 30  # Mark offline after this

# Subdomains
API_DOMAIN = "api.mycreativity.nl"
ADMIN_DOMAIN = "admin.mycreativity.nl"
PUBLIC_DOMAIN = "booth.mycreativity.nl"


# ---------------------------------------------------------------------------
# Card layout config loader
# ---------------------------------------------------------------------------

_card_layout_cache: dict[str, Any] | None = None


def load_card_layout() -> dict[str, Any]:
    """Load the shared card layout configuration.

    Searches for ``card_layout.json`` next to this file, or at common
    deployment paths.  Caches the result for subsequent calls.

    Returns:
        Parsed JSON dict with canvas, branding, and layout definitions.
    """
    global _card_layout_cache
    if _card_layout_cache is not None:
        return _card_layout_cache

    search_paths = [
        Path(__file__).parent / "card_layout.json",          # Dev: shared/
        Path("/opt/photobooth/shared/card_layout.json"),      # Pi deploy
    ]

    for path in search_paths:
        if path.exists():
            try:
                _card_layout_cache = json.loads(path.read_text())
                logger.info("Card layout loaded from %s", path)
                return _card_layout_cache
            except Exception as e:
                logger.warning("Failed to load card layout from %s: %s", path, e)

    logger.warning("card_layout.json not found — using defaults")
    _card_layout_cache = _default_card_layout()
    return _card_layout_cache


def _default_card_layout() -> dict[str, Any]:
    """Hardcoded fallback matching the original print_layouts.py constants."""
    return {
        "canvas": {"width": 1200, "height": 1800},
        "photoRatio": 1.25,
        "padding": 30,
        "outputQuality": 95,
        "branding": {
            "heightPercent": 15,
            "accentLine": {"thickness": 3, "offsetTop": 8},
            "colors": {
                "background": "#1C2028",
                "text": "#EDE8D0",
                "accent": "#FFFFFF",
            },
            "fonts": {
                "titleSize": 36,
                "titleBoldSize": 36,
                "dateSize": 22,
                "lineHeight": 42,
            },
            "logo": {"maxWidth": 300, "maxHeight": 210, "paddingInner": 10},
        },
        "layouts": {
            "single": {
                "label": "Enkele foto",
                "photosNeeded": 1,
                "slots": [{"x": 0, "y": 19.0, "w": 100, "h": 62.0}],
            },
            "strip": {
                "label": "Fotostrip",
                "photosNeeded": 3,
                "slots": [
                    {"x": 0, "y": 2.9, "w": 100, "h": 62.0},
                    {"x": 0, "y": 66.9, "w": 48.7, "h": 30.2},
                    {"x": 51.3, "y": 66.9, "w": 48.7, "h": 30.2},
                ],
            },
            "grid": {
                "label": "Fotogrid",
                "photosNeeded": 4,
                "slots": [
                    {"x": 0, "y": 18.8, "w": 48.7, "h": 30.2},
                    {"x": 51.3, "y": 18.8, "w": 48.7, "h": 30.2},
                    {"x": 0, "y": 51.0, "w": 48.7, "h": 30.2},
                    {"x": 51.3, "y": 51.0, "w": 48.7, "h": 30.2},
                ],
            },
        },
    }

