"""Render every photobooth screen to a PNG screenshot for design review.

Usage:
    python scripts/screenshot_all_screens.py

Saves screenshots to scripts/screenshots/ directory.
"""
import os
import sys

# Kivy environment — headless-friendly
os.environ["KIVY_LOG_LEVEL"] = "warning"
os.environ["KIVY_NO_ARGS"] = "1"
os.environ["KIVY_WINDOW"] = "sdl2"

import kivy
kivy.require("2.3.0")

from kivy.core.window import Window
Window.size = (1280, 800)

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout

# Project imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from photobooth.config import BoothConfig, CameraConfig
from photobooth.i18n import load as load_translations
from photobooth.services.camera import create_camera_service
from photobooth.services.storage import StorageService
from photobooth.ui.themes import get_theme
from photobooth.ui.screens import (
    build_screen_manager,
    SCREEN_SPLASH, SCREEN_IDLE, SCREEN_LAYOUT, SCREEN_FILTER,
    SCREEN_COUNTDOWN, SCREEN_REVIEW, SCREEN_DELIVER, SCREEN_SETTINGS,
    _session, LAYOUT_SINGLE, FILTER_CLASSIC,
)

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


class ScreenshotApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._screens_to_capture = [
            SCREEN_SPLASH,
            SCREEN_IDLE,
            SCREEN_LAYOUT,
            SCREEN_FILTER,
            SCREEN_COUNTDOWN,
            SCREEN_REVIEW,
            SCREEN_DELIVER,
            SCREEN_SETTINGS,
        ]
        self._current_idx = 0

    def build(self):
        cfg = BoothConfig(
            camera=CameraConfig(backend="stub"),
        )
        t = load_translations("nl")
        theme = get_theme("classic")
        camera = create_camera_service("stub")
        storage = StorageService(
            photo_dir="/tmp/photobooth_screenshots",
            database=":memory:",
        )

        # Seed session with fake data for review/deliver screens
        _session.layout = LAYOUT_SINGLE
        _session.filter = FILTER_CLASSIC
        _session.photos_needed = 3
        _session.current_photo_seq = 3
        # Generate visually distinct dummy photos using Pillow
        from PIL import Image as PILImage, ImageDraw
        import io as _io

        def _make_dummy_photo(color1, color2, label_color, w=640, h=480):
            """Create a gradient photo with a circle 'face' for visual testing."""
            img = PILImage.new("RGB", (w, h), color1)
            draw = ImageDraw.Draw(img)
            # Gradient fill
            for y in range(h):
                r = int(color1[0] + (color2[0] - color1[0]) * y / h)
                g = int(color1[1] + (color2[1] - color1[1]) * y / h)
                b = int(color1[2] + (color2[2] - color1[2]) * y / h)
                draw.line([(0, y), (w, y)], fill=(r, g, b))
            # Circle "face" in center
            cx, cy = w // 2, h // 2 - 30
            r = min(w, h) // 4
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=label_color)
            # Eyes
            er = r // 6
            draw.ellipse([cx - r // 3 - er, cy - er, cx - r // 3 + er, cy + er], fill=color1)
            draw.ellipse([cx + r // 3 - er, cy - er, cx + r // 3 + er, cy + er], fill=color1)
            # Smile
            draw.arc([cx - r // 3, cy + er, cx + r // 3, cy + r // 2], 0, 180, fill=color1, width=2)
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()

        _session.captured_photos = [
            _make_dummy_photo((60, 120, 220), (30, 60, 150), (255, 220, 180)),
            _make_dummy_photo((200, 70, 90), (140, 30, 50), (255, 230, 200)),
            _make_dummy_photo((50, 180, 120), (25, 100, 70), (240, 210, 180)),
        ]
        _session.original_photos = list(_session.captured_photos)
        _session.session_id = storage.create_session(
            event_name="Design Review", theme="classic", language="nl", camera="stub",
        )

        self._dummy_photos = list(_session.captured_photos)
        self._dummy_originals = list(_session.original_photos)
        self._dummy_session_id = _session.session_id

        self._root = build_screen_manager(
            t=t, theme=theme, video_path=None,
            camera=camera, storage=storage, config=cfg,
        )

        # Start capturing after a brief delay to let first screen render
        Clock.schedule_once(self._start_capturing, 1.0)
        return self._root

    def _start_capturing(self, _dt):
        self._capture_current_screen()

    def _capture_current_screen(self):
        if self._current_idx >= len(self._screens_to_capture):
            print(f"\nAll {len(self._screens_to_capture)} screenshots saved to {SCREENSHOT_DIR}/")
            self.stop()
            return

        screen_name = self._screens_to_capture[self._current_idx]
        print(f"Capturing: {screen_name}...")

        # Re-inject session data for screens that need photos
        # (The idle screen's on_enter resets the session)
        if screen_name in (SCREEN_REVIEW, SCREEN_DELIVER):
            _session.captured_photos = list(self._dummy_photos)
            _session.original_photos = list(self._dummy_originals)
            _session.session_id = self._dummy_session_id
            _session.layout = LAYOUT_SINGLE
            _session.filter = FILTER_CLASSIC
            _session.photos_needed = 3
            _session.current_photo_seq = 3

        # Navigate to screen
        # Find the ScreenManager inside the root FloatLayout
        sm = None
        for child in self._root.children:
            from kivy.uix.screenmanager import ScreenManager
            if isinstance(child, ScreenManager):
                sm = child
                break

        if sm:
            sm.current = screen_name

        # Wait for render, then screenshot
        Clock.schedule_once(lambda dt: self._take_screenshot(screen_name), 0.8)

    def _take_screenshot(self, screen_name):
        filepath = os.path.join(SCREENSHOT_DIR, f"{screen_name}.png")
        Window.screenshot(name=filepath)
        # Kivy's screenshot() adds a counter prefix, let's find the actual file
        # Actually let's use the export_to_png approach
        self._root.export_to_png(filepath)
        print(f"  -> {filepath}")

        self._current_idx += 1
        Clock.schedule_once(lambda dt: self._capture_current_screen(), 0.5)


if __name__ == "__main__":
    ScreenshotApp().run()
