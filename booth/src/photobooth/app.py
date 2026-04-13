"""Kivy application shell.

This module defines the main Kivy App subclass. It wires together the UI
screens, camera service, storage, and processing pipeline.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

# Configure Kivy BEFORE importing it — order matters.
os.environ.setdefault("KIVY_LOG_LEVEL", "info")
os.environ.setdefault("KIVY_NO_ARGS", "1")  # Don't let Kivy consume sys.argv

import kivy  # noqa: E402
kivy.require("2.3.0")

from kivy.app import App  # noqa: E402
from kivy.core.window import Window  # noqa: E402

from photobooth.config import apply_overrides  # noqa: E402
from photobooth.i18n import load as load_translations  # noqa: E402
from photobooth.services.camera import create_camera_service  # noqa: E402
from photobooth.services.led import LedService, LedConfig as LedServiceConfig  # noqa: E402
from photobooth.services.storage import StorageService  # noqa: E402
from photobooth.ui.screens import build_screen_manager  # noqa: E402
from photobooth.ui.themes import get_theme, register_theme_fonts  # noqa: E402

if TYPE_CHECKING:
    from photobooth.config import BoothConfig

logger = logging.getLogger(__name__)


class PhotoboothApp(App):
    """Main application class.

    Responsibilities:
        - Apply window/display configuration
        - Initialise translations, theme, camera, and storage
        - Build the root widget (ScreenManager)
        - Manage lifecycle (start → running → stop)
    """

    def __init__(self, config: BoothConfig, **kwargs) -> None:
        self._booth_config = config
        self._camera = None
        self._storage = None
        self._led = None
        self._agent = None
        super().__init__(**kwargs)

    @property
    def booth_config(self) -> BoothConfig:
        return self._booth_config

    @property
    def camera(self):
        return self._camera

    @property
    def storage(self):
        return self._storage

    def build(self):
        """Called by Kivy to construct the widget tree."""
        cfg = self._booth_config
        self.title = cfg.app.name
        self._apply_window_settings()

        # Initialise storage FIRST — we need DB overrides before camera init
        self._storage = StorageService(
            photo_dir=cfg.storage.photo_dir,
            database=cfg.storage.database,
        )

        # Apply SQLite settings overrides (user changes made in Settings screen)
        overrides = self._storage.get_all_settings()
        if overrides:
            cfg = apply_overrides(cfg, overrides)
            self._booth_config = cfg
            logger.info("Applied %d setting override(s) from database", len(overrides))

        # Load translations and theme (after overrides so language/theme changes apply)
        t = load_translations(cfg.app.language)
        theme = get_theme(cfg.app.theme)
        register_theme_fonts(theme)

        # Initialise camera service (after overrides so backend switch applies)
        camera_kwargs = {
            "device_index": cfg.camera.device_index,
            "preview_fps": cfg.camera.preview_fps,
            "capture_quality": cfg.camera.capture_quality,
        }
        # Only pass kwargs relevant to the backend
        if cfg.camera.backend == "stub":
            camera_kwargs = {}
        elif cfg.camera.backend == "gphoto2":
            camera_kwargs = {
                "preview_fps": cfg.camera.preview_fps,
                "capture_quality": cfg.camera.capture_quality,
                "iso": cfg.camera.iso,
                "aperture": cfg.camera.aperture,
                "shutter_speed": cfg.camera.shutter_speed,
            }

        logger.info("Camera backend requested: %s", cfg.camera.backend)
        try:
            self._camera = create_camera_service(cfg.camera.backend, **camera_kwargs)
            logger.info("Camera service: %s (backend=%s)", self._camera.name, cfg.camera.backend)
        except Exception as e:
            logger.warning("Failed to create camera '%s': %s. Falling back to stub.", cfg.camera.backend, e)
            self._camera = create_camera_service("stub")

        # Pre-warm camera in background so it's ready when user taps START
        if hasattr(self._camera, "warm_up"):
            self._camera.warm_up()

        # Initialise LED service
        led_cfg = cfg.led
        self._led = LedService(LedServiceConfig(
            enabled=led_cfg.enabled,
            led_count=led_cfg.led_count,
            gpio_pin=led_cfg.gpio_pin,
            brightness=led_cfg.brightness,
            flash_brightness=led_cfg.flash_brightness,
        ))

        # Resolve background video path
        video_path = self._resolve_video_path(cfg.app.background_video)

        # Bind Ctrl+Q for clean quit
        Window.bind(on_keyboard=self._on_keyboard_down)

        # Start admin server agent (if configured)
        server_cfg = getattr(cfg, "server", None)
        if server_cfg and getattr(server_cfg, "enabled", False):
            try:
                from photobooth.services.agent import BoothAgent
                self._agent = BoothAgent({
                    "url": server_cfg.url,
                    "booth_id": server_cfg.booth_id,
                    "booth_name": server_cfg.booth_name,
                    "heartbeat_interval": getattr(server_cfg, "heartbeat_interval", 10),
                    "reconnect_delay": getattr(server_cfg, "reconnect_delay", 5),
                    "reconnect_max_delay": getattr(server_cfg, "reconnect_max_delay", 60),
                })
                self._agent.start()
            except Exception as e:
                logger.warning("Failed to start booth agent: %s", e)

        return build_screen_manager(
            t=t,
            theme=theme,
            video_path=video_path,
            camera=self._camera,
            storage=self._storage,
            config=cfg,
            led=self._led,
        )

    def _resolve_video_path(self, video_setting: str) -> str | None:
        """Resolve the background video path from config."""
        if not video_setting:
            return None

        from pathlib import Path

        path = Path(video_setting)
        if path.is_absolute() and path.exists():
            return str(path)

        rel_path = Path.cwd() / video_setting
        if rel_path.exists():
            return str(rel_path)

        print(f"Warning: background video not found: {video_setting}")
        return None

    def _apply_window_settings(self) -> None:
        """Configure the Kivy window from booth config."""
        cfg = self._booth_config.app

        if cfg.fullscreen:
            # On Pi kiosk (no window manager), fullscreen="auto" can
            # create wrong-sized windows.  Force borderless + exact size.
            Window.borderless = True
            Window.size = (cfg.width, cfg.height)
            Window.left = 0
            Window.top = 0
        else:
            Window.size = (cfg.width, cfg.height)
            Window.fullscreen = False

    def _on_keyboard_down(self, window, key, scancode, codepoint, modifiers) -> bool:
        """Handle keyboard shortcuts.

        Ctrl+Q / Cmd+Q → clean quit.
        """
        if codepoint == "q" and ("ctrl" in modifiers or "meta" in modifiers):
            logger.info("Quit requested (Ctrl+Q)")
            self.stop()
            return True
        return False

    def on_stop(self) -> None:
        """Clean up resources when the app exits."""
        if self._agent:
            self._agent.stop()
            logger.info("Booth agent stopped")

        if self._led:
            self._led.shutdown()
            logger.info("LED service shut down")

        if self._camera:
            self._camera.stop_preview()
            if hasattr(self._camera, "release"):
                self._camera.release()
            logger.info("Camera released")

        if self._storage:
            self._storage.close()
            logger.info("Storage closed")
