"""Screen management for the photobooth flow.

The booth follows a linear user journey per session::

    Idle → Layout → Filter → [Countdown → Capture] × N → Review → Idle

Where N depends on the layout chosen (single=1, strip=3).

A persistent live-preview layer sits *behind* the screens so the camera
feed (or an idle video loop) is always visible as a background.

Architecture
------------
- ``LivePreviewLayer``: Looping video when idle, live camera during flow.
- ``OverlayLayer``: Static semi-transparent layer between bg and screens.
- ``BaseBoothScreen``: Abstract base with fade transitions, shared services.
- ``SettingsScreen``: Hidden admin screen via 5s long-press on idle.
"""

from __future__ import annotations

import io
import logging
import threading
from typing import TYPE_CHECKING

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image as UixImage
from kivy.uix.screenmanager import (
    NoTransition,
    Screen,
    ScreenManager,
)
from kivy.uix.label import Label

from kivy.uix.widget import Widget
from kivy.graphics import (
    Color, Ellipse, Line, Rectangle, RoundedRectangle, Triangle,
)

from photobooth.ui.components import BoothButton

if TYPE_CHECKING:
    from photobooth.config import BoothConfig
    from photobooth.i18n import Translations
    from photobooth.services.camera import CameraService
    from photobooth.services.led import LedService
    from photobooth.services.storage import StorageService
    from photobooth.ui.themes import ThemeData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reusable loading overlay
# ---------------------------------------------------------------------------

class LoadingOverlay(FloatLayout):
    """Full-screen frosted-glass overlay with a spinning ring and status text.

    Usage::

        overlay = LoadingOverlay(theme)
        parent.add_widget(overlay)
        overlay.show("Verwerken...")      # show with message
        overlay.update("Foto's opslaan")  # update message
        overlay.hide()                    # fade out and remove

    The spinner is a rotating arc drawn on canvas.  The overlay blocks
    touch events to prevent user interaction during processing.
    """

    def __init__(self, theme, **kwargs) -> None:
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        self.opacity = 0
        self._theme = theme
        self._spin_angle = 0
        self._spin_event = None

        # Semi-transparent dark backdrop
        with self.canvas.before:
            self._bg_color = Color(0.08, 0.08, 0.15, 0.85)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Spinner ring (drawn via canvas)
        self._spinner_widget = Widget(
            size_hint=(None, None), size=(80, 80),
            pos_hint={"center_x": 0.5, "center_y": 0.55},
        )
        self._spinner_widget.bind(pos=self._draw_spinner, size=self._draw_spinner)
        self.add_widget(self._spinner_widget)

        # Status message
        self._message = Label(
            text="",
            font_size="22sp",
            bold=True,
            color=theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.42},
            size_hint=(0.8, 0.1),
            halign="center",
            valign="middle",
        )
        self._message.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self.add_widget(self._message)

        # Subtle hint below message
        self._hint = Label(
            text="",
            font_size="15sp",
            color=(*theme.colors.text_muted[:3], 0.6),
            pos_hint={"center_x": 0.5, "center_y": 0.36},
            size_hint=(0.8, 0.05),
            halign="center",
        )
        self._hint.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self.add_widget(self._hint)

    def _update_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _draw_spinner(self, *_args) -> None:
        w = self._spinner_widget
        w.canvas.clear()
        cx, cy = w.center_x, w.center_y
        radius = min(w.width, w.height) / 2 - 4

        with w.canvas:
            # Background ring (dim)
            Color(*self._theme.colors.text_muted[:3], 0.2)
            Line(circle=(cx, cy, radius), width=3)

            # Spinning arc (accent colour)
            accent = self._theme.colors.accent
            Color(*accent[:3], 1)
            Line(
                ellipse=(
                    cx - radius, cy - radius,
                    radius * 2, radius * 2,
                    self._spin_angle, self._spin_angle + 100,
                ),
                width=3.5,
                cap="round",
            )

    def _tick_spinner(self, dt) -> None:
        self._spin_angle = (self._spin_angle + 6) % 360
        self._draw_spinner()

    def show(self, message: str = "", hint: str = "") -> None:
        """Show the overlay with a fade-in animation."""
        self._message.text = message
        self._hint.text = hint
        Animation.cancel_all(self)
        Animation(opacity=1, duration=0.3, t="out_cubic").start(self)
        if not self._spin_event:
            self._spin_event = Clock.schedule_interval(self._tick_spinner, 1 / 30)

    def update(self, message: str, hint: str = "") -> None:
        """Update the status message while the overlay is visible."""
        self._message.text = message
        if hint:
            self._hint.text = hint

    def hide(self, remove: bool = True) -> None:
        """Fade out the overlay. Optionally remove from parent."""
        if self._spin_event:
            self._spin_event.cancel()
            self._spin_event = None
        anim = Animation(opacity=0, duration=0.3, t="in_cubic")
        if remove:
            def _remove(*_args):
                if self.parent:
                    self.parent.remove_widget(self)
            anim.bind(on_complete=_remove)
        anim.start(self)

    def on_touch_down(self, touch) -> bool:
        """Block all touches while visible."""
        if self.opacity > 0.1:
            return True
        return super().on_touch_down(touch)


# ---------------------------------------------------------------------------
# Screen name constants
# ---------------------------------------------------------------------------

SCREEN_SPLASH = "splash"
SCREEN_EVENT_REQUIRED = "event_required"
SCREEN_IDLE = "idle"
SCREEN_LAYOUT = "layout"
SCREEN_FILTER = "filter"
SCREEN_COUNTDOWN = "countdown"
SCREEN_CAPTURE = "capture"
SCREEN_REVIEW = "review"
SCREEN_DELIVER = "deliver"
SCREEN_PRINT = "print"
SCREEN_SETTINGS = "settings"
SCREEN_PINCODE = "pincode"

SCREEN_FLOW = [
    SCREEN_SPLASH,
    SCREEN_EVENT_REQUIRED,
    SCREEN_IDLE,
    SCREEN_LAYOUT,
    SCREEN_FILTER,
    SCREEN_COUNTDOWN,
    SCREEN_CAPTURE,
    SCREEN_REVIEW,
    SCREEN_DELIVER,
    SCREEN_PRINT,
]

# Layout options — determines photos_per_session
LAYOUT_SINGLE = "single"
LAYOUT_STRIP = "strip"

LAYOUT_PHOTO_COUNT = {
    LAYOUT_SINGLE: 1,
    LAYOUT_STRIP: 3,
}

# Filter presets
FILTER_NONE = "none"


# ---------------------------------------------------------------------------
# Live preview background layer
# ---------------------------------------------------------------------------

class LivePreviewLayer(FloatLayout):
    """Full-screen background: looping video when idle, live camera
    preview during the photo flow."""

    def __init__(
        self,
        bg_color: tuple[float, ...] = (0.08, 0.08, 0.12, 1.0),
        video_path: str | None = None,
        camera: CameraService | None = None,
        preview_fps: int = 15,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._video_widget = None
        self._camera = camera
        self._preview_fps = preview_fps
        self._preview_event = None
        self._camera_active = False

        # Solid colour fallback
        with self.canvas.before:
            Color(*bg_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        # Camera preview image (hidden initially)
        self._preview_image = UixImage(
            size_hint=(1, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            fit_mode="fill",
            opacity=0,
        )
        self._preview_image.on_touch_down = lambda *a: False
        self.add_widget(self._preview_image)

        # Video background
        if video_path:
            self._setup_video(video_path)

    def _setup_video(self, video_path: str) -> None:
        import os
        if not os.path.isfile(video_path):
            logger.warning("Background video not found: %s", video_path)
            return
        try:
            from kivy.uix.video import Video
            self._video_widget = Video(
                source=video_path,
                state="play",
                volume=0,
                options={"eos": "loop"},
                fit_mode="fill",
                size_hint=(1, 1),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                preview="",  # Suppress image-loader probe on the mp4 file
            )
            self._video_widget.on_touch_down = lambda *a: False
            self.add_widget(self._video_widget)
        except Exception:
            logger.warning("Could not load background video", exc_info=True)

    def _update_rect(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def start_camera_preview(self) -> None:
        """Switch from video to live camera preview."""
        if not self._camera or self._camera_active:
            return
        self._camera_active = True
        self._camera.start_preview()

        if self._video_widget:
            self._video_widget.state = "pause"
            self._video_widget.opacity = 0
        self._preview_image.opacity = 1

        self._preview_event = Clock.schedule_interval(
            self._poll_camera_frame, 1.0 / self._preview_fps,
        )
        logger.info("Camera preview started")

    def stop_camera_preview(self) -> None:
        """Switch back from camera to video."""
        if not self._camera_active:
            return
        self._camera_active = False
        if self._preview_event:
            self._preview_event.cancel()
            self._preview_event = None
        try:
            self._camera.stop_preview()
        except Exception as e:
            logger.warning("Camera stop_preview failed (offline?): %s", e)

        # Always resume video, even if camera is gone
        self._preview_image.opacity = 0
        if self._video_widget:
            self._video_widget.opacity = 1
            self._video_widget.state = "play"
        logger.info("Camera preview stopped, video resumed")

    def set_preview_filter(self, filter_name: str) -> None:
        """Set the filter to apply to live preview frames.

        The filter is applied in the camera's background thread on the
        raw numpy frame — much faster than doing a JPEG round-trip.

        Args:
            filter_name: One of 'color', 'bw', 'sepia'.
        """
        self._preview_filter = filter_name
        # Push filter to camera service for background-thread processing
        if self._camera and hasattr(self._camera, 'preview_filter'):
            self._camera.preview_filter = filter_name

    def _poll_camera_frame(self, _dt) -> None:
        if not self._camera:
            return
        frame_data = self._camera.get_preview_frame()
        if frame_data is None:
            return
        try:
            # Filter is already applied in the camera background thread
            core_img = CoreImage(io.BytesIO(frame_data), ext="jpg")
            # Mirror the preview only for webcams (not DSLR)
            # Webcam preview should look like a mirror; DSLR is already correct
            if getattr(self._camera, 'name', '') == 'Webcam':
                core_img.texture.flip_horizontal()
            self._preview_image.texture = core_img.texture
        except Exception:
            pass

    def pause_video(self) -> None:
        if self._video_widget:
            self._video_widget.state = "pause"

    def resume_video(self) -> None:
        if self._video_widget and not self._camera_active:
            self._video_widget.state = "play"

    def show_crop_guide(self, ratio: float = 1.4, accent_color: tuple = (0.76, 0.60, 0.34, 1)) -> None:
        """Show a crop guide overlay indicating the 7:5 photo area.

        Draws semi-transparent dark bars over the areas that will be
        cropped out, leaving the center 7:5 area bright.  A thin
        accent-colored border marks the crop boundary.

        Args:
            ratio: Target width/height ratio (default 7:5 = 1.4).
            accent_color: RGBA tuple for the crop border color.
        """
        if hasattr(self, "_crop_guide") and self._crop_guide:
            return  # Already showing

        self._crop_guide = Widget(
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )
        self._crop_guide._ratio = ratio
        self._crop_guide._accent = accent_color
        self._crop_guide.bind(pos=self._draw_crop_guide, size=self._draw_crop_guide)
        self.add_widget(self._crop_guide)

    def hide_crop_guide(self) -> None:
        """Remove the crop guide overlay."""
        if hasattr(self, "_crop_guide") and self._crop_guide:
            self.remove_widget(self._crop_guide)
            self._crop_guide = None

    def _draw_crop_guide(self, *_args) -> None:
        """Redraw the crop guide bars and border."""
        from kivy.graphics import Line as KivyLine
        w = self._crop_guide
        if not w or w.width <= 1:
            return

        w.canvas.clear()
        vw, vh = w.width, w.height
        current_ratio = vw / vh

        ratio = w._ratio
        accent = w._accent

        if current_ratio > ratio:
            # Preview is wider — crop left and right
            crop_w = vh * ratio
            bar_w = (vw - crop_w) / 2
            with w.canvas:
                Color(0, 0, 0, 0.55)
                Rectangle(pos=(w.x, w.y), size=(bar_w, vh))
                Rectangle(pos=(w.x + vw - bar_w, w.y), size=(bar_w, vh))
                # Border around crop area
                Color(*accent)
                KivyLine(
                    rectangle=(w.x + bar_w, w.y, crop_w, vh),
                    width=1.5,
                )
        else:
            # Preview is taller — crop top and bottom
            crop_h = vw / ratio
            bar_h = (vh - crop_h) / 2
            with w.canvas:
                Color(0, 0, 0, 0.55)
                Rectangle(pos=(w.x, w.y), size=(vw, bar_h))
                Rectangle(pos=(w.x, w.y + vh - bar_h), size=(vw, bar_h))
                # Border around crop area
                Color(*accent)
                KivyLine(
                    rectangle=(w.x, w.y + bar_h, vw, crop_h),
                    width=1.5,
                )


# ---------------------------------------------------------------------------
# Shared overlay layer
# ---------------------------------------------------------------------------

class OverlayLayer(Widget):
    """Static semi-transparent overlay between video/camera and screens."""

    def __init__(self, overlay_color: tuple[float, ...], **kwargs) -> None:
        super().__init__(**kwargs)
        with self.canvas:
            Color(*overlay_color)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *_args) -> None:
        self._rect.pos = self.pos
        self._rect.size = self.size

    def on_touch_down(self, touch):
        # Always pass touches through — this is a visual-only layer
        return False

    def on_touch_up(self, touch):
        return False

    def on_touch_move(self, touch):
        return False


# ---------------------------------------------------------------------------
# Base screen
# ---------------------------------------------------------------------------

class BaseBoothScreen(Screen):
    """Abstract base for all booth screens."""

    def __init__(
        self,
        t: Translations,
        theme: ThemeData,
        camera: CameraService | None = None,
        storage: StorageService | None = None,
        config: BoothConfig | None = None,
        preview_layer: LivePreviewLayer | None = None,
        led: LedService | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.t = t
        self.theme = theme
        self.camera = camera
        self.storage = storage
        self.config = config
        self.preview_layer = preview_layer
        self.led = led

        # Camera status indicator — small dot top-left
        self._cam_dot = Widget(size_hint=(None, None), size=(12, 12),
                               pos_hint={"x": 0.01, "top": 0.98})
        with self._cam_dot.canvas:
            self._cam_dot_color = Color(0.3, 0.3, 0.3, 0.8)
            self._cam_dot_circle = Ellipse(
                pos=self._cam_dot.pos, size=self._cam_dot.size)
        self._cam_dot.bind(
            pos=lambda w, p: setattr(self._cam_dot_circle, 'pos', p),
            size=lambda w, s: setattr(self._cam_dot_circle, 'size', s))
        self.add_widget(self._cam_dot)

    def _update_cam_dot(self, *_args) -> None:
        """Set dot colour: green = camera connected, red = not."""
        connected = False
        if self.camera:
            try:
                connected = getattr(self.camera, '_camera', None) is not None
            except Exception:
                pass
        if connected:
            self._cam_dot_color.rgba = (0.2, 0.9, 0.2, 0.8)  # green
        else:
            self._cam_dot_color.rgba = (0.9, 0.2, 0.2, 0.8)  # red

    def on_pre_enter(self, *args) -> None:
        self.opacity = 0

    def on_enter(self, *args) -> None:
        self._update_cam_dot()
        Animation.cancel_all(self, "opacity")
        anim = Animation(
            opacity=1,
            duration=self.theme.animation.transition_duration,
            t="out_cubic",
        )
        anim.start(self)

    def navigate_to(self, screen_name: str) -> None:
        if not self.manager:
            return
        manager = self.manager
        target = screen_name
        Animation.cancel_all(self, "opacity")
        anim = Animation(
            opacity=0,
            duration=self.theme.animation.transition_duration,
            t="in_cubic",
        )
        anim.bind(on_complete=lambda *_: setattr(manager, "current", target))
        anim.start(self)

    # ------ inactivity timer helpers (opt-in for screens that need them) ----

    def _start_inactivity_timer(self, timeout: float = 30.0) -> None:
        self._cancel_inactivity_timer()
        self._inactivity_timeout = timeout
        self._inactivity_event = Clock.schedule_once(
            self._on_inactivity_timeout, timeout
        )

    def _reset_inactivity_timer(self, *_args) -> None:
        if getattr(self, "_inactivity_event", None):
            self._cancel_inactivity_timer()
            self._inactivity_event = Clock.schedule_once(
                self._on_inactivity_timeout, self._inactivity_timeout
            )

    def _cancel_inactivity_timer(self) -> None:
        ev = getattr(self, "_inactivity_event", None)
        if ev:
            ev.cancel()
            self._inactivity_event = None

    def _on_inactivity_timeout(self, _dt) -> None:
        self.navigate_to(SCREEN_IDLE)


# ---------------------------------------------------------------------------
# Session state — shared across screens during a photo session
# ---------------------------------------------------------------------------

class SessionState:
    """Mutable session state passed between screens.

    Created fresh for each tap-to-start, holds the user's choices
    and captured photos until the session completes.

    Retake support: ``retake_target`` is set to the 0-based index of
    the photo to redo.  When set, the countdown/capture loop captures
    a single frame and replaces that slot rather than appending.
    Retakes are unlimited.
    """

    def __init__(self) -> None:
        self.session_id: int | None = None
        self.event_id: int | None = None  # Active event ID
        self.layout: str = LAYOUT_SINGLE
        self.filter: str = FILTER_NONE
        self.photos_needed: int = 1
        self.current_photo_seq: int = 1
        self.captured_photos: list[bytes] = []
        self.original_photos: list[bytes] = []  # Unprocessed originals for undo
        # Retake support
        self.retake_target: int | None = None  # 0-based index
        # Post-processing state
        self.polish_applied: dict[str, bool] = {
            "retouch": False,
            "brightness": False,
            "glamour": False,
        }
        # Print composite (generated on accept)
        self.print_composite: bytes | None = None

    def reset(self) -> None:
        self.session_id = None
        # event_id is NOT reset — it persists across sessions
        self.layout = LAYOUT_SINGLE
        self.filter = FILTER_NONE
        self.photos_needed = 1
        self.current_photo_seq = 1
        self.captured_photos = []
        self.original_photos = []
        self.retake_target = None
        self.polish_applied = {"retouch": False, "brightness": False, "glamour": False}
        self.print_composite = None


# Singleton session state — shared across all screens
_session = SessionState()


def _get_layout_ratio(layout: str = "") -> float:
    """Get the photo ratio for the given layout from shared config.

    Each layout can define its own photoRatio (e.g. single=4:5 portrait,
    strip/grid=5:4 landscape). Falls back to 1.25 if not found.
    """
    from photobooth.services.print_layouts import _CFG
    layout = layout or _session.layout
    layout_cfg = _CFG.get("layouts", {}).get(layout, {})
    return layout_cfg.get("photoRatio", 1.25)

# ---------------------------------------------------------------------------
# Reusable UI: Big touchable card
# ---------------------------------------------------------------------------

class TouchCard(FloatLayout):
    """A large, rounded, touchable card with a drawn icon + text label.

    The ``icon_draw`` callback receives ``(widget, x, y, w, h)`` and should
    draw canvas instructions for the icon area.  If not provided, the
    ``icon_text`` string is shown as a plain Label fallback.
    """

    def __init__(
        self,
        label_text: str,
        bg_color: tuple[float, ...],
        text_color: tuple[float, ...],
        callback,
        icon_text: str = "",
        icon_draw=None,
        subtitle_text: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._callback = callback
        self._icon_draw = icon_draw

        with self.canvas.before:
            # Higher opacity for better contrast on kiosk screen
            bg_rgba = (*bg_color[:3], bg_color[3] * 0.72 if len(bg_color) > 3 else 0.72)
            self._bg_color = Color(*bg_rgba)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[20],
            )
        self.bind(pos=self._update, size=self._update)

        # Icon area — drawn via canvas or fallback text
        self._icon_widget = Widget(
            size_hint=(0.75, 0.55),
            pos_hint={"center_x": 0.5, "center_y": 0.58},
        )
        self._icon_widget.bind(pos=self._draw_icon, size=self._draw_icon)
        self.add_widget(self._icon_widget)

        if not icon_draw and icon_text:
            # Fallback: plain text label
            self._icon_label = Label(
                text=icon_text,
                font_size="44sp",
                bold=True,
                color=text_color,
                pos_hint={"center_x": 0.5, "center_y": 0.58},
                size_hint=(1, 1),
            )
            self.add_widget(self._icon_label)

        label_cy = 0.19 if subtitle_text else 0.12
        self._label = Label(
            text=label_text,
            font_size="26sp",
            bold=True,
            color=text_color,
            pos_hint={"center_x": 0.5, "center_y": label_cy},
            size_hint=(0.9, 0.15),
            text_size=(None, None),
            halign="center",
            valign="middle",
        )
        self._label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self.add_widget(self._label)

        if subtitle_text:
            subtitle_color = (*text_color[:3], 0.6)
            self._subtitle = Label(
                text=subtitle_text,
                font_size="19sp",
                color=subtitle_color,
                pos_hint={"center_x": 0.5, "center_y": 0.12},
                size_hint=(0.9, 0.12),
                text_size=(None, None),
                halign="center",
                valign="middle",
            )
            self._subtitle.bind(size=lambda w, s: setattr(w, 'text_size', s))
            self.add_widget(self._subtitle)

    def _update(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _draw_icon(self, *_args) -> None:
        if self._icon_draw:
            w = self._icon_widget
            w.canvas.clear()
            self._icon_draw(w, w.x, w.y, w.width, w.height)

    def on_touch_down(self, touch) -> bool:
        if self.collide_point(*touch.pos):
            self._callback()
            return True
        return super().on_touch_down(touch)


def _draw_print_frame(widget, x, y, w, h):
    """Draw the outer print frame (shared by all layout icons).

    Returns (frame_x, frame_y, frame_w, frame_h, bar_h) for placing
    photo slots inside.
    """
    cx, cy = x + w / 2, y + h / 2
    # Print proportions: 10:15 portrait → 2:3 ratio
    frame_h = min(h * 0.88, w * 0.88 * 1.5)
    frame_w = frame_h / 1.5
    fx = cx - frame_w / 2
    fy = cy - frame_h / 2
    bar_h = frame_h * 0.15  # Branding bar

    with widget.canvas:
        # Paper shadow
        Color(0, 0, 0, 0.3)
        RoundedRectangle(
            pos=(fx + 2, fy - 2), size=(frame_w, frame_h), radius=[3],
        )
        # White paper
        Color(1, 1, 1, 0.95)
        RoundedRectangle(
            pos=(fx, fy), size=(frame_w, frame_h), radius=[3],
        )
        # Branding bar (dark)
        Color(0.11, 0.13, 0.16, 0.9)
        RoundedRectangle(
            pos=(fx, fy), size=(frame_w, bar_h), radius=[0, 0, 3, 3],
        )
        # Gold accent line above branding
        Color(0.76, 0.60, 0.34, 1)
        Rectangle(
            pos=(fx + 3, fy + bar_h - 1), size=(frame_w - 6, 2),
        )

    return fx, fy, frame_w, frame_h, bar_h


def _make_layout_preview(layout_id: str):
    """Return an icon-draw callback that renders slot positions from card_layout.json."""
    from photobooth.services.print_layouts import _CFG

    def _draw(widget, x, y, w, h):
        fx, fy, fw, fh, bar_h = _draw_print_frame(widget, x, y, w, h)
        pad = fw * 0.06
        photo_area_w = fw - pad * 2
        photo_area_h = fh - bar_h - pad * 2
        slots = _CFG.get("layouts", {}).get(layout_id, {}).get("slots", [])
        with widget.canvas:
            for slot in slots:
                sw = slot["w"] / 100 * photo_area_w
                sh = slot["h"] / 100 * photo_area_h
                sx = fx + pad + slot["x"] / 100 * photo_area_w
                # Kivy origin is bottom-left; slot y=0 is the TOP of the photo area
                sy = fy + bar_h + pad + (1 - (slot["y"] + slot["h"]) / 100) * photo_area_h
                Color(0.50, 0.50, 0.48, 1)
                RoundedRectangle(pos=(sx, sy), size=(sw, sh), radius=[2])

    return _draw


_draw_layout_preview_single = _make_layout_preview("single")
_draw_layout_preview_strip = _make_layout_preview("strip")



def _draw_classic_icon(widget, x, y, w, h):
    """Draw a clean, bright lens icon for the Classic (no filter) option."""
    cx, cy = x + w / 2, y + h / 2
    r = min(w, h) * 0.35
    with widget.canvas:
        # Outer ring
        Color(0.4, 0.55, 0.95, 1)
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
        # Inner bright core
        Color(0.5, 0.75, 1.0, 0.9)
        Ellipse(pos=(cx - r * 0.6, cy - r * 0.6), size=(r * 1.2, r * 1.2))
        # Highlight dot
        Color(1, 1, 1, 0.7)
        Ellipse(pos=(cx - r * 0.2, cy + r * 0.1), size=(r * 0.4, r * 0.4))


def _draw_vintage_love_icon(widget, x, y, w, h):
    """Draw a warm, faded circle with heart accent for Vintage Love."""
    cx, cy = x + w / 2, y + h / 2
    r = min(w, h) * 0.35
    with widget.canvas:
        # Warm faded base
        Color(0.82, 0.65, 0.52, 1)
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
        # Inner warm glow
        Color(0.92, 0.78, 0.62, 0.8)
        Ellipse(pos=(cx - r * 0.65, cy - r * 0.65), size=(r * 1.3, r * 1.3))
        # Soft pink accent
        Color(0.90, 0.55, 0.55, 0.5)
        Ellipse(pos=(cx - r * 0.3, cy - r * 0.3), size=(r * 0.6, r * 0.6))


def _draw_glamour_bw_icon(widget, x, y, w, h):
    """Draw a dramatic half-tone circle for Glamour B&W."""
    cx, cy = x + w / 2, y + h / 2
    r = min(w, h) * 0.35
    with widget.canvas:
        # White base
        Color(0.95, 0.95, 0.95, 1)
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
        # Dark half (left side)
        Color(0.1, 0.1, 0.1, 1)
        Ellipse(pos=(cx - r, cy - r), size=(r, r * 2))
        # Vignette-like ring
        Color(0.3, 0.3, 0.3, 0.3)
        Ellipse(pos=(cx - r * 0.9, cy - r * 0.9), size=(r * 1.8, r * 1.8))


def _draw_golden_hour_icon(widget, x, y, w, h):
    """Draw a warm golden gradient circle for Golden Hour."""
    cx, cy = x + w / 2, y + h / 2
    r = min(w, h) * 0.35
    with widget.canvas:
        # Outer warm amber
        Color(0.95, 0.72, 0.30, 1)
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
        # Inner bright gold
        Color(1.0, 0.85, 0.45, 0.85)
        Ellipse(pos=(cx - r * 0.6, cy - r * 0.6), size=(r * 1.2, r * 1.2))
        # Highlight
        Color(1, 0.95, 0.7, 0.6)
        Ellipse(pos=(cx - r * 0.25, cy + r * 0.05), size=(r * 0.5, r * 0.5))


def _draw_party_pop_icon(widget, x, y, w, h):
    """Draw a vibrant, multi-colored burst for Party Pop."""
    cx, cy = x + w / 2, y + h / 2
    r = min(w, h) * 0.35
    with widget.canvas:
        # Hot pink base
        Color(0.92, 0.25, 0.55, 1)
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
        # Electric blue accent (top-right)
        Color(0.20, 0.55, 1.0, 0.7)
        Ellipse(pos=(cx - r * 0.1, cy - r * 0.2), size=(r * 1.1, r * 1.1))
        # Neon green spark (bottom-left)
        Color(0.30, 1.0, 0.55, 0.5)
        Ellipse(pos=(cx - r * 0.8, cy - r * 0.7), size=(r * 0.8, r * 0.8))
        # Bright center flash
        Color(1, 1, 1, 0.45)
        Ellipse(pos=(cx - r * 0.25, cy - r * 0.25), size=(r * 0.5, r * 0.5))


def _make_lut_icon_draw(filter_id: str):
    """Generate a unique icon draw function for a LUT filter.

    Uses a hash of the filter name to produce deterministic but varied
    colors for each LUT — no two LUT icons look the same.
    """
    # Generate hue from filter name hash (0..1)
    h = (hash(filter_id) % 360) / 360.0
    import colorsys
    r1, g1, b1 = colorsys.hls_to_rgb(h, 0.45, 0.7)
    r2, g2, b2 = colorsys.hls_to_rgb((h + 0.1) % 1.0, 0.6, 0.5)

    def _draw(widget, x, y, w, ht):
        cx, cy = x + w / 2, y + ht / 2
        r = min(w, ht) * 0.35
        with widget.canvas:
            # Outer ring
            Color(r1, g1, b1, 1)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            # Inner accent
            Color(r2, g2, b2, 0.8)
            Ellipse(pos=(cx - r * 0.55, cy - r * 0.55), size=(r * 1.1, r * 1.1))
            # "LUT" marker — small diamond
            Color(1, 1, 1, 0.6)
            Ellipse(pos=(cx - r * 0.2, cy - r * 0.2), size=(r * 0.4, r * 0.4))
    return _draw

# ---------------------------------------------------------------------------
# Concrete screens
# ---------------------------------------------------------------------------


class SplashScreen(BaseBoothScreen):
    """Startup splash screen with logo and loading animation.

    Shown immediately on app launch while services initialize in the
    background.  Transitions to idle after a short delay.
    """

    _MIN_DISPLAY_TIME = 2.5  # Minimum seconds to show splash

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_SPLASH, **kwargs)

        # Dark background — fill the whole screen
        with self.canvas.before:
            Color(*self.theme.colors.background)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Logo image
        import os
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(__file__)))),
            "assets", "images", "logo.png",
        )
        self._logo = UixImage(
            source=logo_path,
            size_hint=(0.4, 0.4),
            pos_hint={"center_x": 0.5, "center_y": 0.55},
            fit_mode="contain",
        )
        self.add_widget(self._logo)

        # Loading dots label
        self._loading_label = Label(
            text="Loading",
            font_size=self.theme.typography.subtitle_size,
            color=self.theme.colors.text_muted,
            pos_hint={"center_x": 0.5, "center_y": 0.22},
        )
        self.add_widget(self._loading_label)

        self._dot_count = 0
        self._dot_event = None
        self._transition_event = None

    def _update_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def on_enter(self, *args) -> None:
        super().on_enter(*args)
        self._dot_count = 0
        self._dot_event = Clock.schedule_interval(self._animate_dots, 0.4)
        # Fade in the logo
        self._logo.opacity = 0
        Animation(opacity=1.0, duration=0.6, t="out_cubic").start(self._logo)
        # Preload LUT filters in background so FilterScreen doesn't stutter
        threading.Thread(
            target=self._preload_luts,
            name="lut-preload",
            daemon=True,
        ).start()
        # Schedule transition to idle
        self._transition_event = Clock.schedule_once(
            self._go_to_idle, self._MIN_DISPLAY_TIME,
        )

    @staticmethod
    def _preload_luts() -> None:
        """Preload all .cube LUT files into the global cache."""
        try:
            from photobooth.services.processing import get_lut_registry
            registry = get_lut_registry()
            luts = registry.available_luts()
            logger.info("Preloaded %d LUT filters", len(luts))
        except Exception as e:
            logger.warning("LUT preload failed: %s", e)

    def on_leave(self, *args) -> None:
        if self._dot_event:
            self._dot_event.cancel()
            self._dot_event = None
        if self._transition_event:
            self._transition_event.cancel()
            self._transition_event = None

    def _animate_dots(self, _dt) -> None:
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        self._loading_label.text = f"Loading{dots}"

    def _go_to_idle(self, _dt) -> None:
        """Route to idle if an event is active, else to event-required gate."""
        if self.storage:
            active_event = self.storage.get_active_event()
            if active_event:
                _session.event_id = active_event["id"]
                logger.info(
                    "Splash complete — active event: %s (id=%d)",
                    active_event["name"], active_event["id"],
                )
                self.navigate_to(SCREEN_IDLE)
                return

        logger.info("Splash complete — no active event, showing gate")
        self.navigate_to(SCREEN_EVENT_REQUIRED)


class EventRequiredScreen(BaseBoothScreen):
    """Gate screen shown when no event is active.

    Blocks the user from using the booth and directs them to settings
    to create a new event.  The "Naar instellingen" button navigates
    directly to the settings screen.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_EVENT_REQUIRED, **kwargs)

        # Semi-opaque background
        with self.canvas.before:
            Color(*self.theme.colors.background)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Warning icon — large exclamation in a circle
        self._icon_widget = Widget(
            size_hint=(0.15, 0.12),
            pos_hint={"center_x": 0.5, "center_y": 0.68},
        )
        self._icon_widget.bind(pos=self._draw_icon, size=self._draw_icon)
        self.add_widget(self._icon_widget)

        # Title
        self.add_widget(Label(
            text=self.t("event.required_title"),
            font_size=self.theme.typography.title_size,
            bold=True,
            color=self.theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.52},
        ))

        # Message
        self.add_widget(Label(
            text=self.t("event.required_message"),
            font_size=self.theme.typography.subtitle_size,
            color=self.theme.colors.text_muted,
            pos_hint={"center_x": 0.5, "center_y": 0.44},
        ))

        # CTA button
        self.add_widget(BoothButton(
            text=self.t("event.go_to_settings"),
            theme=self.theme,
            variant="primary",
            on_press=self._go_to_settings,
            size_hint=(0.4, 0.10),
            pos_hint={"center_x": 0.5, "center_y": 0.32},
        ))

    def _update_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _draw_icon(self, *_args) -> None:
        w = self._icon_widget
        if w.width <= 1:
            return
        w.canvas.clear()
        cx, cy = w.center_x, w.center_y
        r = min(w.width, w.height) * 0.4
        with w.canvas:
            # Circle outline
            Color(*self.theme.colors.secondary[:3], 0.8)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            # Inner dark circle
            Color(*self.theme.colors.background[:3], 0.9)
            inner_r = r * 0.85
            Ellipse(pos=(cx - inner_r, cy - inner_r), size=(inner_r * 2, inner_r * 2))
        # Exclamation mark via a label
        if not hasattr(self, "_excl_label"):
            self._excl_label = Label(
                text="!",
                font_size="48sp",
                bold=True,
                color=self.theme.colors.secondary,
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            )
            self._icon_widget.add_widget(self._excl_label)

    def on_enter(self, *args) -> None:
        super().on_enter(*args)
        # Re-check in case an event was created via settings
        if self.storage:
            active_event = self.storage.get_active_event()
            if active_event:
                _session.event_id = active_event["id"]
                self.navigate_to(SCREEN_IDLE)

    def _go_to_settings(self) -> None:
        self.navigate_to(SCREEN_SETTINGS)


def read_pushed_event() -> dict | None:
    """Return the event pushed from the admin (cached in event_card.json).

    Returns the parsed dict (event_uid, event_name, display_date, …) or
    ``None`` when no event has been pushed / the cache is unreadable.
    """
    import json
    from pathlib import Path

    data_dir = Path("/opt/photobooth/data")
    if not data_dir.exists():
        data_dir = Path("data")
    card_path = data_dir / "event_card.json"
    if not card_path.exists():
        return None
    try:
        card = json.loads(card_path.read_text())
    except Exception:
        return None
    return card if card.get("event_name") else None


class IdleScreen(BaseBoothScreen):
    """Welcome screen — massive pulsing CTA, settings button bottom-right.

    Designed for maximum visibility in dark environments: high-contrast
    colors and a bold, unmissable "START" button that pulses.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_IDLE, **kwargs)

        # Coupled-event name (top of screen) — filled in on_enter.
        self._event_label = Label(
            text="",
            font_size=self.theme.typography.subtitle_size,
            bold=True,
            color=self.theme.colors.primary_light,
            pos_hint={"center_x": 0.5, "center_y": 0.9},
        )
        self.add_widget(self._event_label)

        # Title — bright white, large
        title = Label(
            text=self.t("idle.title"),
            font_size="56sp",
            bold=True,
            color=self.theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.75},
        )
        self.add_widget(title)

        # Massive CTA button — accent colored, rounded
        # All graphics drawn on container.canvas.before + bind to self
        # to avoid the (0,0) rendering bug.
        self._btn_container = FloatLayout(
            size_hint=(0.55, 0.18),
            pos_hint={"center_x": 0.5, "center_y": 0.42},
        )

        # Draw glow + button fill directly on container canvas
        with self._btn_container.canvas.before:
            self._glow_color = Color(*self.theme.colors.accent_glow)
            self._glow_rect = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[40])
            Color(*self.theme.colors.accent)
            self._btn_rect = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[30])

        self._btn_container.bind(
            pos=self._sync_btn_gfx, size=self._sync_btn_gfx,
        )

        # Button text
        self._btn_label = Label(
            text=self.t("idle.tap_to_start"),
            font_size="42sp",
            bold=True,
            color=(1, 1, 1, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self._btn_container.add_widget(self._btn_label)

        self.add_widget(self._btn_container)

        # Subtitle underneath
        self._subtitle = Label(
            text=self.t("idle.subtitle"),
            font_size=self.theme.typography.subtitle_size,
            color=self.theme.colors.text_muted,
            pos_hint={"center_x": 0.5, "center_y": 0.22},
        )
        self.add_widget(self._subtitle)

        # Small settings icon — bottom-right, subtle but visible
        self._settings_btn = BoothButton(
            text="Instellingen",
            theme=self.theme,
            variant="ghost",
            on_press=self._open_pincode,
            font_size="18sp",
            size_hint=(0.18, 0.065),
            pos_hint={"right": 0.98, "y": 0.02},
        )
        self.add_widget(self._settings_btn)

    def _sync_btn_gfx(self, *_args) -> None:
        """Keep glow and button rects aligned with the container."""
        c = self._btn_container
        # Glow extends beyond the button
        glow_pad_x = c.width * 0.08
        glow_pad_y = c.height * 0.20
        self._glow_rect.pos = (c.x - glow_pad_x, c.y - glow_pad_y)
        self._glow_rect.size = (c.width + glow_pad_x * 2, c.height + glow_pad_y * 2)
        # Button fill
        self._btn_rect.pos = c.pos
        self._btn_rect.size = c.size

    def on_enter(self, *args) -> None:
        super().on_enter(*args)
        # Show the coupled (admin-pushed) event, if any
        event = read_pushed_event()
        self._event_label.text = event["event_name"] if event else self.t("event.no_event")
        # Reset session state
        _session.reset()
        # Ensure camera preview is stopped and video resumes
        # (covers returning from capture error or any screen)
        if self.preview_layer:
            self.preview_layer.stop_camera_preview()
            self.preview_layer.set_preview_filter("classic")
        # LED: warm ambient glow
        if self.led:
            self.led.mood()

        # Pulsing animation on the glow color
        self._pulse_anim = Animation(
            opacity=0.7, duration=0.8, t="in_out_sine"
        ) + Animation(
            opacity=1.0, duration=0.8, t="in_out_sine"
        )
        self._pulse_anim.repeat = True
        self._pulse_anim.start(self._btn_container)

        # Camera power-saving: release after 2 minutes idle
        self._camera_sleeping = False
        self._sleep_event = Clock.schedule_once(
            self._sleep_camera, 120,  # 2 minutes
        )

    def on_leave(self, *args) -> None:
        Animation.cancel_all(self._btn_container)
        self._cancel_hold()
        # Cancel sleep timer
        if hasattr(self, '_sleep_event') and self._sleep_event:
            self._sleep_event.cancel()
            self._sleep_event = None

    def _sleep_camera(self, _dt) -> None:
        """Release camera connection to save battery."""
        if self.camera and hasattr(self.camera, 'release'):
            self.camera.release()
            self._camera_sleeping = True
            logger.info("Camera released for power saving (idle timeout)")

    def _wake_camera(self) -> None:
        """Reconnect camera after sleep."""
        if self._camera_sleeping and self.camera:
            if hasattr(self.camera, 'warm_up'):
                self.camera.warm_up()
                logger.info("Camera waking up from sleep")
            self._camera_sleeping = False

    def on_touch_down(self, touch) -> bool:
        if self.manager and self.manager.current == self.name:
            # Let settings button handle its own touch first
            if super().on_touch_down(touch):
                return True
            # Wake sleeping camera on any touch
            if hasattr(self, '_camera_sleeping') and self._camera_sleeping:
                self._wake_camera()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch) -> bool:
        if self.manager and self.manager.current == self.name:
            # Settings button handles its own touch_up — if it consumed, stop
            if super().on_touch_up(touch):
                return True
            # Any other tap starts a session
            self.navigate_to(SCREEN_LAYOUT)
            return True
        return super().on_touch_up(touch)

    def _open_pincode(self) -> None:
        self.navigate_to(SCREEN_PINCODE)


class LayoutScreen(BaseBoothScreen):
    """Choose a photo layout: Single Shot or Collage (3 photos).

    The choice determines how many photos are taken per session.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_LAYOUT, **kwargs)

        title = Label(
            text=self.t("layout.title"),
            font_size=self.theme.typography.title_size,
            bold=True,
            color=self.theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.88},
        )
        self.add_widget(title)

        # Two layout cards side by side
        cards_container = FloatLayout(
            size_hint=(0.72, 0.62),
            pos_hint={"center_x": 0.5, "center_y": 0.47},
        )

        card_w = 0.44
        positions = [0.25, 0.75]
        layouts = [
            (LAYOUT_SINGLE, self.t("layout.single"), self.t("layout.single_hint"), _draw_layout_preview_single),
            (LAYOUT_STRIP, self.t("layout.strip"), self.t("layout.strip_hint"), _draw_layout_preview_strip),
        ]

        for (layout_id, label, hint, draw_fn), cx in zip(layouts, positions):
            card = TouchCard(
                label_text=label,
                subtitle_text=hint,
                bg_color=self.theme.colors.surface,
                text_color=self.theme.colors.text,
                callback=lambda lid=layout_id: self._select_layout(lid),
                icon_draw=draw_fn,
                size_hint=(card_w, 1.0),
                pos_hint={"center_x": cx, "center_y": 0.5},
            )
            cards_container.add_widget(card)

        self.add_widget(cards_container)

        # Filter hint — always shown, filters are not event-dependent
        filter_hint_color = (*self.theme.colors.text[:3], 0.55)
        filter_hint = Label(
            text=self.t("layout.filter_hint"),
            font_size="24sp",
            color=filter_hint_color,
            pos_hint={"center_x": 0.5, "center_y": 0.10},
            size_hint=(0.8, 0.08),
            halign="center",
            valign="middle",
        )
        filter_hint.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.add_widget(filter_hint)

        # Back button — always visible, bottom-left: triangle icon + label
        back_container = FloatLayout(
            size_hint=(0.18, 0.08),
            pos_hint={"x": 0.02, "center_y": 0.06},
        )
        back_container.bind(on_touch_down=self._on_back_touch)

        back_icon = Widget(
            size_hint=(0.22, 1.0),
            pos_hint={"x": 0, "center_y": 0.5},
        )

        def _draw_triangle(w, *_):
            w.canvas.clear()
            cx = w.x + w.width / 2
            cy = w.y + w.height / 2
            th = w.height * 0.38
            tw = th * 0.75
            with w.canvas:
                Color(*filter_hint_color)
                Triangle(points=[
                    cx + tw / 2, cy + th / 2,
                    cx + tw / 2, cy - th / 2,
                    cx - tw / 2, cy,
                ])

        back_icon.bind(pos=_draw_triangle, size=_draw_triangle)
        back_container.add_widget(back_icon)

        back_label = Label(
            text=self.t("common.back"),
            font_size="18sp",
            color=filter_hint_color,
            pos_hint={"right": 1.0, "center_y": 0.5},
            size_hint=(0.78, 1.0),
            halign="left",
            valign="middle",
        )
        back_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        back_container.add_widget(back_label)
        self.add_widget(back_container)

    def _on_back_touch(self, widget, touch) -> bool:
        if widget.collide_point(*touch.pos):
            self.navigate_to(SCREEN_IDLE)
            return True
        return False

    def on_enter(self, *args) -> None:
        super().on_enter(*args)
        # Start camera preview so users can see themselves
        if self.preview_layer:
            self.preview_layer.start_camera_preview()

    def on_leave(self, *args) -> None:
        super().on_leave(*args)

    def _select_layout(self, layout_id: str) -> None:
        _session.layout = layout_id
        _session.photos_needed = LAYOUT_PHOTO_COUNT[layout_id]
        logger.info("Layout selected: %s (%d photos)", layout_id, _session.photos_needed)
        self.navigate_to(SCREEN_FILTER)


class FilterScreen(BaseBoothScreen):
    """Choose a filter from a curated list of .cube LUT filters.

    Displays a horizontally swipeable strip of filter cards at the bottom
    of the screen. The live camera preview fills the top.  Tapping a card
    applies the filter to the preview instantly.

    All filters are .cube LUT files in ``assets/luts/``.
    """

    # Static, curated filter registry: (filter_id, label, icon_draw_fn)
    # filter_id matches the .cube filename stem in assets/luts/
    _FILTER_DEFS: list[tuple[str, str, object]] = []

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_FILTER, **kwargs)
        self._selected_filter = "none"

        # Title at the top
        title = Label(
            text=self.t("filter.title"),
            font_size=self.theme.typography.title_size,
            bold=True,
            color=self.theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.92},
        )
        self.add_widget(title)

        # Build the curated filter list
        self._all_filters = [
            ("none",          self.t("filter.classic"),      _draw_classic_icon),
            ("vintage_love",  self.t("filter.vintage_love"), _draw_vintage_love_icon),
            ("glamour_bw",    self.t("filter.glamour_bw"),   _draw_glamour_bw_icon),
            ("golden_hour",   self.t("filter.golden_hour"),  _draw_golden_hour_icon),
            ("party_pop",     self.t("filter.party_pop"),    _draw_party_pop_icon),
            ("film_noir",     "Film Noir",                   _make_lut_icon_draw("film_noir")),
            ("rose",          "Rosé",                        _make_lut_icon_draw("rose")),
            ("sunset_bliss",  "Sunset",                      _make_lut_icon_draw("sunset_bliss")),
            ("tropical",      "Tropical",                    _make_lut_icon_draw("tropical")),
        ]

        # Horizontal scrollable filter strip
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.boxlayout import BoxLayout

        scroll = ScrollView(
            size_hint=(0.96, 0.20),
            pos_hint={"center_x": 0.5, "y": 0.14},
            do_scroll_y=False,
            do_scroll_x=True,
            bar_width=0,              # hide scrollbar
            scroll_type=["content"],  # swipe to scroll
        )

        # Calculate fixed card width in pixels — use dp for scaling
        from kivy.metrics import dp
        card_w_dp = dp(130)
        gap_dp = dp(10)
        n = len(self._all_filters)
        total_w = n * card_w_dp + (n - 1) * gap_dp + gap_dp * 2  # padding on sides

        self._cards_box = BoxLayout(
            orientation="horizontal",
            size_hint=(None, 1),
            width=total_w,
            spacing=gap_dp,
            padding=[gap_dp, 0, gap_dp, 0],
        )

        for filter_id, label, draw_fn in self._all_filters:
            card = TouchCard(
                label_text=label,
                bg_color=self.theme.colors.surface,
                text_color=self.theme.colors.text,
                callback=lambda fid=filter_id: self._preview_filter(fid),
                icon_draw=draw_fn,
                size_hint=(None, 1),
                width=card_w_dp,
            )
            # Keep cards square: width follows height after layout
            card.bind(height=lambda w, h: setattr(w, 'width', h))
            self._cards_box.add_widget(card)

        scroll.add_widget(self._cards_box)

        # Update BoxLayout total width when cards become square
        # (width follows height after layout)
        def _update_box_width(card_inst, new_width):
            self._cards_box.width = (
                n * new_width + (n - 1) * gap_dp + gap_dp * 2
            )
        # Bind to first card's width — all cards resize together
        if self._cards_box.children:
            self._cards_box.children[-1].bind(width=_update_box_width)
        self.add_widget(scroll)

        self._swipe_hint = Label(
            text="← " + self.t("filter.title") + " →",
            font_size="16sp",
            color=(*self.theme.colors.text_muted[:3], 0.5),
            pos_hint={"center_x": 0.5, "y": 0.10},
        )
        self.add_widget(self._swipe_hint)

        logger.info("[Filters] %d filters available", len(self._all_filters))

        # Confirm button at bottom-center
        self._done_btn = BoothButton(
            text=self.t("review.accept"),
            theme=self.theme,
            variant="primary",
            on_press=self._confirm,
            size_hint=(0.3, 0.09),
            pos_hint={"center_x": 0.5, "y": 0.02},
        )
        self.add_widget(self._done_btn)

    def _preview_filter(self, filter_id: str) -> None:
        """Apply filter to live preview without navigating."""
        self._selected_filter = filter_id
        logger.info("[Filter preview] %s", filter_id)
        if self.preview_layer:
            self.preview_layer.set_preview_filter(filter_id)
        # Update card borders to show selection
        self._update_card_selection()

    def _update_card_selection(self) -> None:
        """Draw a gold border around the selected filter card."""
        accent = self.theme.colors.accent
        for card in self._cards_box.children:
            card.canvas.after.clear()
        for card, (fid, _, _) in zip(
            reversed(list(self._cards_box.children)), self._all_filters
        ):
            if fid == self._selected_filter:
                with card.canvas.after:
                    Color(*accent[:3], 1)
                    Line(
                        rounded_rectangle=(
                            card.x + 2, card.y + 2,
                            card.width - 4, card.height - 4,
                            18,
                        ),
                        width=2.5,
                    )
                break

    def _confirm(self) -> None:
        """Commit the selected filter and proceed to countdown."""
        _session.filter = self._selected_filter
        logger.info("[Filter selected] %s", self._selected_filter)
        self.navigate_to(SCREEN_COUNTDOWN)


class CountdownScreen(BaseBoothScreen):
    """Animated countdown with a massive arrow pointing to the camera lens.

    Features:
    - 5-second countdown for the first photo, 3-second "panic gap" between shots
    - Massive pulsing arrow pointing UP toward the physical camera lens
    - "Look at the lens!" text to reinforce the visual cue
    - Photo counter for multi-shot sessions (e.g. "Foto 2 van 3")
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_COUNTDOWN, **kwargs)
        self._remaining = 5
        self._tick_event = None

        # --- Massive arrow drawn via canvas (avoids glyph rendering issues) ---
        self._arrow_widget = Widget(
            size_hint=(0.12, 0.18),
            pos_hint={"center_x": 0.5, "center_y": 0.82},
        )
        self._arrow_widget.bind(
            pos=self._draw_arrow, size=self._draw_arrow,
        )
        self.add_widget(self._arrow_widget)

        # "Look here!" text under the arrow
        self._look_label = Label(
            text=self.t("countdown.look_at_lens"),
            font_size="28sp",
            bold=True,
            color=self.theme.colors.accent,
            pos_hint={"center_x": 0.5, "center_y": 0.65},
        )
        self.add_widget(self._look_label)

        # Countdown digit — large and centered
        self._digit_label = Label(
            text="5",
            font_size=self.theme.typography.countdown_size,
            bold=True,
            color=self.theme.colors.primary_light,
            pos_hint={"center_x": 0.5, "center_y": 0.42},
        )
        self.add_widget(self._digit_label)

        # "Get ready!" text
        self._ready_label = Label(
            text=self.t("countdown.get_ready"),
            font_size=self.theme.typography.subtitle_size,
            color=self.theme.colors.text_muted,
            pos_hint={"center_x": 0.5, "center_y": 0.28},
        )
        self.add_widget(self._ready_label)

        # Photo counter for multi-shot sessions
        self._counter_label = Label(
            text="",
            font_size=self.theme.typography.body_size,
            color=self.theme.colors.text_muted,
            pos_hint={"center_x": 0.5, "center_y": 0.18},
        )
        self.add_widget(self._counter_label)

    def on_pre_enter(self, *args) -> None:
        super().on_pre_enter(*args)
        # Create session on first photo (skip on retake)
        if _session.retake_target is None and _session.current_photo_seq == 1:
            _session.captured_photos = []
            if self.storage:
                # Get active event name for the session record
                active_event = self.storage.get_active_event()
                event_name = active_event["name"] if active_event else ""

                _session.session_id = self.storage.create_session(
                    event_name=event_name,
                    theme=self.config.app.theme if self.config else "",
                    language=self.config.app.language if self.config else "",
                    camera=self.config.camera.backend if self.config else "",
                    event_id=_session.event_id,
                    layout=_session.layout,
                    filter_name=_session.filter,
                )

    def on_enter(self, *args) -> None:
        super().on_enter(*args)

        # Show crop guide on the camera preview (ratio depends on layout)
        if self.preview_layer:
            ratio = _get_layout_ratio()
            self.preview_layer.show_crop_guide(
                ratio=ratio,
                accent_color=self.theme.colors.accent,
            )

        # Update counter — retake shows different text
        if _session.retake_target is not None:
            self._counter_label.text = self.t(
                "review.retake_counter",
                n=str(_session.retake_target + 1),
            )
        elif _session.photos_needed > 1:
            self._counter_label.text = self.t(
                "countdown.photo_counter",
                current=str(_session.current_photo_seq),
                total=str(_session.photos_needed),
            )
        else:
            self._counter_label.text = ""

        # Dynamic duration: 5s for first photo, 3s "panic gap" for subsequent
        if _session.current_photo_seq == 1:
            duration = self.config.countdown.first_countdown if self.config else 5
        else:
            duration = self.config.countdown.between_shots if self.config else 3

        self._remaining = duration
        self._total = duration
        self._digit_label.text = str(self._remaining)
        self._digit_label.opacity = 1.0
        self._animate_digit()

        # Start the pulsing arrow animation
        self._start_arrow_animation()

        # Trigger autofocus + exposure calibration in background
        # (people step back from touchscreen → AF locks at correct distance)
        if self.camera and hasattr(self.camera, 'prepare_for_capture'):
            threading.Thread(
                target=self.camera.prepare_for_capture,
                daemon=True,
            ).start()

        self._tick_event = Clock.schedule_interval(self._tick, 1.0)

    def on_leave(self, *args) -> None:
        # Hide crop guide
        if self.preview_layer:
            self.preview_layer.hide_crop_guide()
        if self._tick_event:
            self._tick_event.cancel()
            self._tick_event = None
        Animation.cancel_all(self._digit_label)
        Animation.cancel_all(self._arrow_widget)
        Animation.cancel_all(self._look_label)

    def _draw_arrow(self, *_args) -> None:
        """Draw a large upward-pointing triangle on the arrow widget's canvas."""
        from kivy.graphics import Triangle as KivyTriangle
        w = self._arrow_widget
        w.canvas.clear()
        with w.canvas:
            Color(*self.theme.colors.accent)
            # Triangle: bottom-left, bottom-right, top-center
            KivyTriangle(points=[
                w.x, w.y,
                w.x + w.width, w.y,
                w.x + w.width / 2, w.y + w.height,
            ])

    def _tick(self, _dt) -> None:
        self._remaining -= 1
        if self._remaining > 0:
            self._digit_label.text = str(self._remaining)
            self._animate_digit()
            # LED: countdown colors (green → yellow → red)
            if self.led:
                self.led.countdown(self._remaining, self._total)
            # LED: switch to bright white for last second (pre-illuminate)
            if self._remaining == 1 and self.led:
                self.led.pre_capture()
        else:
            if self._tick_event:
                self._tick_event.cancel()
                self._tick_event = None
            self.navigate_to(SCREEN_CAPTURE)

    def _animate_digit(self) -> None:
        scale = self.theme.animation.countdown_scale
        self._digit_label.opacity = 1.0
        anim = Animation(
            font_size=self._digit_label.font_size * scale,
            opacity=1.0, duration=0.15, t="out_back",
        ) + Animation(
            font_size=self._digit_label.font_size,
            opacity=0.85, duration=0.7, t="in_out_sine",
        )
        Animation.cancel_all(self._digit_label)
        anim.start(self._digit_label)

    def _start_arrow_animation(self) -> None:
        """Pulsing bounce animation on the arrow to draw the eye upward."""
        Animation.cancel_all(self._arrow_widget)
        Animation.cancel_all(self._look_label)

        # Arrow: pulse opacity + gentle vertical bounce via pos_hint
        arrow_anim = Animation(
            opacity=0.5, duration=0.5, t="in_out_sine",
        ) + Animation(
            opacity=1.0, duration=0.5, t="in_out_sine",
        )
        arrow_anim.repeat = True
        arrow_anim.start(self._arrow_widget)

        # "Look here" text pulses in sync
        look_anim = Animation(
            opacity=0.4, duration=0.5, t="in_out_sine",
        ) + Animation(
            opacity=1.0, duration=0.5, t="in_out_sine",
        )
        look_anim.repeat = True
        look_anim.start(self._look_label)


class CaptureScreen(BaseBoothScreen):
    """Takes the photo, saves it, then loops back or proceeds to review.

    Features a full-screen white camera flash effect that fires instantly
    on capture and fades out smoothly — just like a real photo booth.

    Handles both normal capture and retake mode (when
    ``_session.retake_target`` is set).
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_CAPTURE, **kwargs)

        # Full-screen flash overlay — drawn via canvas so it covers everything
        self._flash_widget = Widget(
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
            opacity=0,
        )
        with self._flash_widget.canvas:
            self._flash_color = Color(1, 1, 1, 1)
            self._flash_rect = Rectangle(
                pos=self._flash_widget.pos,
                size=self._flash_widget.size,
            )
        self._flash_widget.bind(
            pos=self._sync_flash_rect,
            size=self._sync_flash_rect,
        )
        self.add_widget(self._flash_widget)

        # Small label in the center (shown briefly after flash fades)
        self._flash_label = Label(
            text=self.t("capture.flash"),
            font_size=self.theme.typography.title_size,
            bold=True,
            color=self.theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            opacity=0,
        )
        self.add_widget(self._flash_label)

    def _sync_flash_rect(self, *_args) -> None:
        self._flash_rect.pos = self._flash_widget.pos
        self._flash_rect.size = self._flash_widget.size

    def on_enter(self, *args) -> None:
        super().on_enter(*args)

        # LED: maximum brightness flash for photo
        if self.led:
            self.led.flash()

        # --- Fire the flash! ---
        # Start fully opaque white, then fade out over 0.6s
        self._flash_widget.opacity = 1.0
        flash_anim = Animation(
            opacity=0.0, duration=0.6, t="out_expo",
        )
        flash_anim.start(self._flash_widget)

        # Show the text label after the flash peaks
        self._flash_label.opacity = 0
        label_anim = Animation(opacity=0, duration=0.2) + Animation(
            opacity=1.0, duration=0.2, t="out_quad",
        )
        label_anim.start(self._flash_label)

        threading.Thread(
            target=self._do_capture,
            name="photo-capture",
            daemon=True,
        ).start()

    def on_leave(self, *args) -> None:
        Animation.cancel_all(self._flash_widget)
        Animation.cancel_all(self._flash_label)

    def _do_capture(self) -> None:
        try:
            jpeg_data = self.camera.capture_photo() if self.camera else b""
            retake_idx = _session.retake_target

            # Center-crop to layout-specific ratio (e.g. 4:5 for single, 5:4 for strip/grid)
            if jpeg_data:
                from photobooth.services.print_layouts import crop_to_ratio
                ratio = _get_layout_ratio()
                jpeg_data = crop_to_ratio(jpeg_data, ratio)

            # Keep unfiltered original for undo/rebuild pipeline
            raw_data = jpeg_data

            # Apply selected filter to captured photo
            logger.info("[Capture] session filter=%r", _session.filter)
            if jpeg_data and _session.filter != "none":
                from photobooth.services.processing import apply_filter_to_jpeg
                jpeg_data = apply_filter_to_jpeg(jpeg_data, _session.filter)
                logger.info("[Capture] Filter '%s' applied to captured photo", _session.filter)
            else:
                logger.info("[Capture] No filter applied (filter=%r)", _session.filter)

            if retake_idx is not None:
                # --- Retake mode: replace a specific frame ---
                seq = retake_idx + 1  # 1-based
                if jpeg_data and self.storage and _session.session_id:
                    self.storage.replace_photo(
                        session_id=_session.session_id,
                        seq=seq,
                        jpeg_data=jpeg_data,
                        event_id=_session.event_id,
                    )
                _session.captured_photos[retake_idx] = jpeg_data
                _session.original_photos[retake_idx] = raw_data
                _session.retake_target = None
                Clock.schedule_once(lambda _: self._after_retake(), 0.5)
            else:
                # --- Normal capture mode ---
                if jpeg_data and self.storage and _session.session_id:
                    self.storage.save_photo(
                        session_id=_session.session_id,
                        seq=_session.current_photo_seq,
                        jpeg_data=jpeg_data,
                        event_id=_session.event_id,
                    )
                _session.captured_photos.append(jpeg_data)
                _session.original_photos.append(raw_data)
                Clock.schedule_once(lambda _: self._after_capture(), 0.5)

        except Exception as e:
            logger.error("Capture failed: %s", e)
            _session.retake_target = None
            Clock.schedule_once(lambda _: self.navigate_to(SCREEN_IDLE), 1.0)

    def _after_capture(self) -> None:
        if _session.current_photo_seq < _session.photos_needed:
            _session.current_photo_seq += 1
            self.navigate_to(SCREEN_COUNTDOWN)
        else:
            _session.current_photo_seq = 1
            self.navigate_to(SCREEN_REVIEW)

    def _after_retake(self) -> None:
        """After a retake, go straight back to review."""
        self.navigate_to(SCREEN_REVIEW)


class ReviewScreen(BaseBoothScreen):
    """Interactive photo review: thumbnails, per-frame retake, and polish.

    After all photos are captured, the user sees every photo as a
    tappable thumbnail.  Tapping a thumbnail initiates a retake for
    that specific frame.  Bottom buttons apply Pillow-based
    post-processing ("Instant Magic").
    """

    _IDLE_TIMEOUT = 90.0  # seconds before auto-returning to idle
    _WARNING_THRESHOLD = 30.0  # show indicator when this many seconds remain
    _URGENT_THRESHOLD = 10.0  # pulse urgently when this many seconds remain

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_REVIEW, **kwargs)

        # --- Solid black background (use Window size for reliable coverage) ---
        from kivy.core.window import Window as KivyWindow
        with self.canvas.before:
            Color(0, 0, 0, 1)
            self._bg_rect = Rectangle(
                pos=(0, 0),
                size=(KivyWindow.width or 4000, KivyWindow.height or 4000),
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

        # --- Title ---
        self._title_label = Label(
            text=self.t("review.title"),
            font_size=self.theme.typography.title_size,
            bold=True,
            color=self.theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.96},
        )
        self.add_widget(self._title_label)

        # --- Retake hint (compact, right under title) ---
        self._hint_label = Label(
            text=self.t("review.retake_hint"),
            font_size="16sp",
            color=self.theme.colors.text_muted,
            pos_hint={"center_x": 0.5, "center_y": 0.91},
        )
        self.add_widget(self._hint_label)

        # --- Thumbnail container — maximize photo area ---
        self._thumb_container = FloatLayout(
            size_hint=(0.98, 0.68),
            pos_hint={"center_x": 0.5, "center_y": 0.54},
        )
        self.add_widget(self._thumb_container)

        # --- Bottom button bar (touch-friendly height) ---
        self._btn_bar = FloatLayout(
            size_hint=(0.96, 0.13),
            pos_hint={"center_x": 0.5, "center_y": 0.08},
        )
        self.add_widget(self._btn_bar)

        # --- Status label (inline feedback) ---
        self._status_label = Label(
            text="",
            font_size="16sp",
            color=self.theme.colors.success,
            pos_hint={"center_x": 0.5, "center_y": 0.17},
        )
        self.add_widget(self._status_label)

        # --- Timeout progress bar (thin bar at top, hidden initially) ---
        self._timeout_bar = Widget(
            size_hint=(1.0, None),
            height=4,
            pos_hint={"x": 0, "top": 1.0},
            opacity=0,
        )
        self._timeout_bar_color = None
        self._timeout_bar_rect = None
        with self._timeout_bar.canvas:
            self._timeout_bar_color = Color(0.95, 0.72, 0.30, 0.9)  # warm amber
            self._timeout_bar_rect = RoundedRectangle(
                pos=self._timeout_bar.pos,
                size=self._timeout_bar.size,
                radius=[2],
            )
        self._timeout_bar.bind(
            pos=self._update_timeout_bar_rect,
            size=self._update_timeout_bar_rect,
        )
        self.add_widget(self._timeout_bar)

        # Internal state
        self._thumb_widgets: list[UixImage] = []
        self._timeout_event = None
        self._warning_event = None
        self._urgent_event = None
        self._bar_anim: Animation | None = None

    def on_enter(self, *args) -> None:
        super().on_enter(*args)

        # LED: celebration animation
        if self.led:
            self.led.celebrate()

        # Stop camera preview and pause background video — review screen
        # should show a clean dark background behind the photo thumbnails.
        if self.preview_layer:
            self.preview_layer.stop_camera_preview()
            self.preview_layer.pause_video()

        self._status_label.text = ""
        self._build_thumbnails()
        self._build_buttons()

        # Reset and start the rolling idle timeout
        self._reset_idle_timeout()

    def on_leave(self, *args) -> None:
        self._cancel_timeout()
        Animation.cancel_all(self._timeout_bar)
        # Resume background video for next screens
        if self.preview_layer:
            self.preview_layer.resume_video()

    def on_touch_down(self, touch):
        """Reset idle timer on any touch (rolling expiration)."""
        self._reset_idle_timeout()
        return super().on_touch_down(touch)

    # ----- rolling idle timeout ---------------------------------------------

    def _reset_idle_timeout(self) -> None:
        """Cancel existing timer and start a fresh countdown."""
        self._cancel_timeout()

        # Reset visual state
        Animation.cancel_all(self._timeout_bar)
        self._timeout_bar.opacity = 0
        self._timeout_bar.size_hint_x = 1.0
        if self._timeout_bar_color:
            self._timeout_bar_color.rgba = (0.95, 0.72, 0.30, 0.9)  # amber

        # Schedule the idle transition (full timeout)
        self._timeout_event = Clock.schedule_once(
            self._go_to_idle, self._IDLE_TIMEOUT,
        )
        # Schedule the warning bar to appear when WARNING_THRESHOLD seconds remain
        warning_delay = self._IDLE_TIMEOUT - self._WARNING_THRESHOLD
        self._warning_event = Clock.schedule_once(
            self._start_warning_bar, warning_delay,
        )

    def _start_warning_bar(self, _dt) -> None:
        """Show the progress bar and animate it smoothly from full to empty."""
        # Fade in
        Animation(opacity=1.0, duration=0.5).start(self._timeout_bar)

        # Smooth continuous shrink over the remaining WARNING_THRESHOLD seconds
        self._bar_anim = Animation(
            size_hint_x=0.0,
            duration=self._WARNING_THRESHOLD,
            t="linear",
        )
        self._bar_anim.start(self._timeout_bar)

        # Schedule color change to red when URGENT_THRESHOLD seconds remain
        urgent_delay = self._WARNING_THRESHOLD - self._URGENT_THRESHOLD
        self._urgent_event = Clock.schedule_once(
            self._start_urgent_pulse, urgent_delay,
        )

    def _start_urgent_pulse(self, _dt) -> None:
        """Switch bar to red in the final seconds."""
        if self._timeout_bar_color:
            self._timeout_bar_color.rgba = (0.92, 0.28, 0.28, 0.95)

    def _cancel_timeout(self) -> None:
        """Cancel all timeout-related scheduled events."""
        if self._timeout_event:
            self._timeout_event.cancel()
            self._timeout_event = None
        if self._warning_event:
            self._warning_event.cancel()
            self._warning_event = None
        if self._urgent_event:
            self._urgent_event.cancel()
            self._urgent_event = None
        if self._bar_anim:
            self._bar_anim.cancel(self._timeout_bar)
            self._bar_anim = None

    def _update_timeout_bar_rect(self, *_args) -> None:
        """Keep the canvas rectangle in sync with the widget."""
        if self._timeout_bar_rect:
            self._timeout_bar_rect.pos = self._timeout_bar.pos
            self._timeout_bar_rect.size = self._timeout_bar.size

    # ----- thumbnail grid --------------------------------------------------

    def _build_thumbnails(self) -> None:
        """Build photo thumbnails with layout-aware arrangement.

        - 1 photo: large centered (portrait for single layout)
        - 3 photos: horizontal row
        - 6 photos: 2×3 grid
        """
        from PIL import Image as PILImage

        self._thumb_container.clear_widgets()
        self._thumb_widgets.clear()

        photos = _session.captured_photos
        count = len(photos)
        if count == 0:
            return

        # Get layout ratio for proper aspect display
        ratio = _get_layout_ratio()
        is_portrait = ratio < 1.0

        # Calculate grid positions based on photo count
        if count == 6:
            # 2×3 grid — 2 columns, 3 rows
            positions = [
                (0.28, 0.82, 0.44, 0.30),  # row 1 left
                (0.72, 0.82, 0.44, 0.30),  # row 1 right
                (0.28, 0.50, 0.44, 0.30),  # row 2 left
                (0.72, 0.50, 0.44, 0.30),  # row 2 right
                (0.28, 0.18, 0.44, 0.30),  # row 3 left
                (0.72, 0.18, 0.44, 0.30),  # row 3 right
            ]
        elif count == 3:
            # 3 in a row
            positions = [
                (0.18, 0.5, 0.30, 0.92),
                (0.50, 0.5, 0.30, 0.92),
                (0.82, 0.5, 0.30, 0.92),
            ]
        else:
            # 1 photo — portrait or landscape based on ratio
            if is_portrait:
                positions = [(0.5, 0.5, 0.42, 0.96)]
            else:
                positions = [(0.5, 0.5, 0.55, 0.96)]

        for idx, photo_data in enumerate(photos):
            if idx >= len(positions):
                break
            cx, cy, cw, ch = positions[idx]

            card = FloatLayout(
                size_hint=(cw, ch),
                pos_hint={"center_x": cx, "center_y": cy},
            )

            # Card background
            with card.canvas.before:
                card._bg_color_instr = Color(*self.theme.colors.surface)
                card._bg_rrect = RoundedRectangle(
                    pos=(0, 0), size=(0, 0), radius=[12],
                )

            def _sync_card_bg(w, *_a):
                if hasattr(w, '_bg_rrect'):
                    w._bg_rrect.pos = w.pos
                    w._bg_rrect.size = w.size
            card.bind(pos=_sync_card_bg, size=_sync_card_bg)

            # Photo image
            img_widget = UixImage(
                size_hint=(0.94, 0.86),
                pos_hint={"center_x": 0.5, "center_y": 0.54},
                allow_stretch=True,
                keep_ratio=True,
            )
            if photo_data:
                try:
                    pil_img = PILImage.open(io.BytesIO(photo_data))
                    pil_img = pil_img.convert("RGBA")
                    from kivy.graphics.texture import Texture
                    tex = Texture.create(size=pil_img.size, colorfmt="rgba")
                    tex.blit_buffer(
                        pil_img.tobytes(), colorfmt="rgba", bufferfmt="ubyte",
                    )
                    tex.flip_vertical()
                    img_widget.texture = tex
                except Exception:
                    pass

            card.add_widget(img_widget)
            self._thumb_widgets.append(img_widget)

            # Photo number badge
            badge = Label(
                text=self.t("review.photo_number", n=str(idx + 1)),
                font_size="20sp",
                bold=True,
                color=(1, 1, 1, 0.9),
                pos_hint={"center_x": 0.5, "center_y": 0.06},
            )
            card.add_widget(badge)

            # Retake tap handler
            def _make_retake_cb(i):
                def _cb(widget, touch):
                    if widget.collide_point(*touch.pos):
                        self._initiate_retake(i)
                        return True
                    return False
                return _cb

            card.on_touch_down = _make_retake_cb(idx).__get__(card)
            self._thumb_container.add_widget(card)

    # ----- button bar -------------------------------------------------------

    def _build_buttons(self) -> None:
        """Create the bottom action buttons with icons.

        Cards are stored as refs so _update_button_states() can
        update colors/icons in-place without a full rebuild.
        """
        self._btn_bar.clear_widgets()

        # --- Effect button definitions ---
        self._effect_defs = [
            ("retouch", self.t("review.auto_retouch"), self._apply_retouch,
             self._draw_retouch_icon),
            ("brightness", self.t("review.brightness"), self._apply_brightness,
             self._draw_brightness_icon),
            ("glamour", self.t("review.glamour"), self._apply_glamour,
             self._draw_glamour_icon),
        ]

        positions = [0.125, 0.375, 0.625]
        self._effect_cards: dict[str, FloatLayout] = {}

        for (key, label, callback, icon_fn), cx in zip(self._effect_defs, positions):
            toggled = _session.polish_applied.get(key, False)

            card = FloatLayout(
                size_hint=(0.20, 1.0),
                pos_hint={"center_x": cx, "center_y": 0.5},
            )

            # Background — start at zero size; _sync_bg positions it
            # after the first layout pass
            bg_color = self.theme.colors.primary if toggled else self.theme.colors.surface
            with card.canvas.before:
                card._bg_color_instr = Color(*bg_color[:3], 0.85)
                card._bg_rect = RoundedRectangle(
                    pos=(0, 0), size=(0, 0), radius=[14],
                )

            def _sync_bg(w, *_a):
                if hasattr(w, '_bg_rect'):
                    w._bg_rect.pos = w.pos
                    w._bg_rect.size = w.size
            card.bind(pos=_sync_bg, size=_sync_bg)

            # Icon area
            icon_widget = Widget(
                size_hint=(0.5, 0.35),
                pos_hint={"center_x": 0.5, "center_y": 0.65},
            )
            card._icon_widget = icon_widget
            card._icon_fn = icon_fn
            card.add_widget(icon_widget)

            # Label
            text_color = (1, 1, 1, 1) if toggled else self.theme.colors.text
            lbl = Label(
                text=label,
                font_size="18sp",
                bold=True,
                color=text_color,
                pos_hint={"center_x": 0.5, "center_y": 0.22},
            )
            card._label = lbl
            card.add_widget(lbl)

            # Touch handling — note: Kivy calls on_touch_down(touch)
            # for plain function overrides (no self arg needed)
            def _make_touch(c, cb):
                def _td(touch):
                    if c.collide_point(*touch.pos):
                        Animation.cancel_all(c, "opacity")
                        c.opacity = 0.7
                        # Don't return True — let parent handle dispatch
                    return False
                def _tu(touch):
                    if c.opacity < 1.0:
                        Animation(opacity=1.0, duration=0.15).start(c)
                    if c.collide_point(*touch.pos):
                        cb()
                    return False
                c.on_touch_down = _td
                c.on_touch_up = _tu
            _make_touch(card, callback)

            self._effect_cards[key] = card
            self._btn_bar.add_widget(card)

        # Accept (primary CTA)
        self._btn_bar.add_widget(BoothButton(
            text=self.t("review.accept"),
            theme=self.theme,
            variant="primary",
            on_press=self._accept,
            size_hint=(0.20, 1.0),
            pos_hint={"center_x": 0.875, "center_y": 0.5},
        ))

        # Schedule icon drawing after first layout pass
        Clock.schedule_once(lambda dt: self._draw_all_icons(), 0)

    def _draw_all_icons(self) -> None:
        """Draw icons for all effect buttons (called after layout)."""
        for key, card in self._effect_cards.items():
            toggled = _session.polish_applied.get(key, False)
            if hasattr(card, '_icon_fn') and hasattr(card, '_icon_widget'):
                card._icon_fn(card._icon_widget, toggled)

    def _update_button_states(self) -> None:
        """Update button colors and icons in-place (no rebuild)."""
        for key, card in self._effect_cards.items():
            toggled = _session.polish_applied.get(key, False)

            # Update bg color
            bg_color = self.theme.colors.primary if toggled else self.theme.colors.surface
            if hasattr(card, '_bg_color_instr'):
                card._bg_color_instr.rgba = (*bg_color[:3], 0.85)

            # Update text color
            text_color = (1, 1, 1, 1) if toggled else self.theme.colors.text
            if hasattr(card, '_label'):
                card._label.color = text_color

            # Redraw icon with correct color
            if hasattr(card, '_icon_fn') and hasattr(card, '_icon_widget'):
                card._icon_fn(card._icon_widget, toggled)

    # ----- icon drawers for effect buttons -----------------------------------

    def _draw_retouch_icon(self, widget, toggled=False) -> None:
        """Draw a sparkle/wand icon for retouch."""
        w = widget
        if w.width <= 1:
            return
        w.canvas.after.clear()
        col = (1, 1, 1, 1) if toggled else self.theme.colors.text
        cx, cy = w.center_x, w.center_y
        s = min(w.width, w.height) * 0.35

        with w.canvas.after:
            Color(*col)
            # Wand line
            Line(points=[cx - s, cy - s, cx + s, cy + s], width=1.8)
            # Sparkle dots
            d = s * 0.18
            for ox, oy in [(s * 0.6, s * 0.2), (s * 0.2, s * 0.6), (-s * 0.3, s * 0.8)]:
                Ellipse(pos=(cx + ox - d / 2, cy + oy - d / 2), size=(d, d))

    def _draw_brightness_icon(self, widget, toggled=False) -> None:
        """Draw a sun/brightness icon."""
        w = widget
        if w.width <= 1:
            return
        w.canvas.after.clear()
        col = (1, 1, 1, 1) if toggled else self.theme.colors.text
        cx, cy = w.center_x, w.center_y
        r = min(w.width, w.height) * 0.2

        with w.canvas.after:
            Color(*col)
            # Center circle
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            # Rays
            import math
            ray_len = r * 1.4
            for angle_deg in range(0, 360, 45):
                a = math.radians(angle_deg)
                x1 = cx + math.cos(a) * (r + 3)
                y1 = cy + math.sin(a) * (r + 3)
                x2 = cx + math.cos(a) * (r + ray_len)
                y2 = cy + math.sin(a) * (r + ray_len)
                Line(points=[x1, y1, x2, y2], width=1.5)

    def _draw_glamour_icon(self, widget, toggled=False) -> None:
        """Draw a diamond/face icon for glamour."""
        w = widget
        if w.width <= 1:
            return
        w.canvas.after.clear()
        col = (1, 1, 1, 1) if toggled else self.theme.colors.text
        cx, cy = w.center_x, w.center_y
        s = min(w.width, w.height) * 0.35

        with w.canvas.after:
            Color(*col)
            # Diamond shape
            # Top half
            Triangle(points=[
                cx - s, cy,
                cx + s, cy,
                cx, cy + s * 1.2,
            ])
            # Bottom half
            Triangle(points=[
                cx - s, cy,
                cx + s, cy,
                cx, cy - s * 1.2,
            ])

    # ----- retake -----------------------------------------------------------

    def _initiate_retake(self, idx: int) -> None:
        """Start retaking frame *idx* (0-based)."""
        logger.info("Retake requested for frame %d", idx + 1)
        _session.retake_target = idx

        # Start camera preview for the retake
        if self.preview_layer:
            self.preview_layer.start_camera_preview()

        self.navigate_to(SCREEN_COUNTDOWN)

    # ----- instant magic ----------------------------------------------------

    def _apply_retouch(self) -> None:
        """Toggle auto-retouch on all captured photos."""
        from photobooth.services.processing import auto_retouch

        if _session.polish_applied["retouch"]:
            _session.polish_applied["retouch"] = False
            self._rebuild_from_originals()
            self._status_label.text = self.t("review.retake_hint")
            logger.info("Retouch removed")
        else:
            for i, photo in enumerate(_session.captured_photos):
                if photo:
                    _session.captured_photos[i] = auto_retouch(photo)
            _session.polish_applied["retouch"] = True
            self._status_label.text = self.t("review.retouch_applied")
            logger.info("Auto-retouch applied to %d photos", len(_session.captured_photos))

        self._update_button_states()
        self._build_thumbnails()
        self._resave_all()

    def _apply_brightness(self) -> None:
        """Toggle brightness boost on all captured photos."""
        from photobooth.services.processing import brightness_boost

        if _session.polish_applied["brightness"]:
            _session.polish_applied["brightness"] = False
            self._rebuild_from_originals()
            self._status_label.text = self.t("review.retake_hint")
            logger.info("Brightness removed")
        else:
            for i, photo in enumerate(_session.captured_photos):
                if photo:
                    _session.captured_photos[i] = brightness_boost(photo)
            _session.polish_applied["brightness"] = True
            self._status_label.text = self.t("review.brightness_applied")
            logger.info("Brightness boost applied to %d photos", len(_session.captured_photos))

        self._update_button_states()
        self._build_thumbnails()
        self._resave_all()

    def _apply_glamour(self) -> None:
        """Toggle glamour enhancement (async — runs in background thread)."""
        if _session.polish_applied["glamour"]:
            _session.polish_applied["glamour"] = False
            self._rebuild_from_originals()
            self._status_label.text = self.t("review.retake_hint")
            logger.info("Glamour removed")
            self._update_button_states()
            self._build_thumbnails()
            self._resave_all()
        else:
            # Show loading indicator
            self._status_label.text = self.t("capture.processing")
            self._btn_bar.disabled = True
            self._btn_bar.opacity = 0.4

            import threading

            def _process():
                from photobooth.services.processing import glamour_enhance, GlamourParams
                params = self._get_glamour_params()
                results = []
                for photo in _session.captured_photos:
                    if photo:
                        results.append(glamour_enhance(photo, params, preview=True))
                    else:
                        results.append(photo)
                # Schedule UI update on main thread
                Clock.schedule_once(lambda dt: self._glamour_done(results), 0)

            threading.Thread(
                target=_process, name="glamour-process", daemon=True,
            ).start()

    def _glamour_done(self, results: list) -> None:
        """Called on main thread when glamour processing completes."""
        _session.captured_photos = results
        _session.polish_applied["glamour"] = True
        self._status_label.text = self.t("review.glamour_applied")
        logger.info("Glamour applied to %d photos", len(results))

        self._btn_bar.disabled = False
        self._btn_bar.opacity = 1.0
        self._update_button_states()
        self._build_thumbnails()
        self._resave_all()

    def _rebuild_from_originals(self) -> None:
        """Rebuild captured_photos from originals with only active effects.

        Re-applies the session filter first, then any active polish effects.
        This ensures the filter is never lost when toggling retouch/brightness.
        """
        from photobooth.services.processing import (
            apply_filter_to_jpeg, auto_retouch, brightness_boost,
            glamour_enhance,
        )

        # Start from unfiltered originals
        _session.captured_photos = list(_session.original_photos)

        # Re-apply the active filter (if not "none")
        if _session.filter != "none":
            for i, photo in enumerate(_session.captured_photos):
                if photo:
                    _session.captured_photos[i] = apply_filter_to_jpeg(
                        photo, _session.filter,
                    )

        if _session.polish_applied["retouch"]:
            for i, photo in enumerate(_session.captured_photos):
                if photo:
                    _session.captured_photos[i] = auto_retouch(photo)

        if _session.polish_applied["brightness"]:
            for i, photo in enumerate(_session.captured_photos):
                if photo:
                    _session.captured_photos[i] = brightness_boost(photo)

        if _session.polish_applied["glamour"]:
            params = self._get_glamour_params()
            for i, photo in enumerate(_session.captured_photos):
                if photo:
                    _session.captured_photos[i] = glamour_enhance(photo, params)

    def _get_glamour_params(self):
        """Read glamour parameters from SQLite storage (matches settings sliders)."""
        from photobooth.services.processing import GlamourParams

        if self.storage:
            return GlamourParams(
                skin_smooth=float(self.storage.get_setting("glamour.skin_smooth", "0.7")),
                warmth=float(self.storage.get_setting("glamour.warmth", "0.5")),
                vignette=float(self.storage.get_setting("glamour.vignette", "0.5")),
                eye_enhance=float(self.storage.get_setting("glamour.eye_enhance", "0.5")),
                makeup=float(self.storage.get_setting("glamour.makeup", "0.5")),
                sparkles=float(self.storage.get_setting("glamour.sparkles", "0.3")),
                soft_glow=float(self.storage.get_setting("glamour.soft_glow", "0.4")),
            )
        # Fallback to defaults
        return GlamourParams()

    def _resave_all(self) -> None:
        """Re-save all photos to storage after processing."""
        if not self.storage or not _session.session_id:
            return
        for i, photo in enumerate(_session.captured_photos):
            if photo:
                self.storage.replace_photo(
                    session_id=_session.session_id,
                    seq=i + 1,
                    jpeg_data=photo,
                    event_id=_session.event_id,
                )

    def _update_bg(self, *_args) -> None:
        """Keep the black background rectangle in sync with the widget."""
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    # ----- accept / timeout -------------------------------------------------

    def _accept(self) -> None:
        """Accept photos — show loading overlay while processing."""
        # Create and show loading overlay
        self._loading = LoadingOverlay(self.theme)
        self.add_widget(self._loading)
        self._loading.show(
            self.t("loading.processing"),
            self.t("loading.please_wait"),
        )
        # Run heavy processing in a background thread
        threading.Thread(target=self._accept_worker, daemon=True).start()

    def _accept_worker(self) -> None:
        """Heavy processing — runs in background thread."""
        try:
            # Step 1: Glamour re-processing
            if _session.polish_applied["glamour"]:
                Clock.schedule_once(lambda _: self._loading.update(
                    self.t("loading.retouch")), 0)
                self._rebuild_from_originals()

            if self.storage and _session.session_id:
                # Step 2: Save final variants
                Clock.schedule_once(lambda _: self._loading.update(
                    self.t("loading.saving")), 0)
                self.storage.save_final_variants(
                    session_id=_session.session_id,
                    event_id=_session.event_id,
                    photos=_session.captured_photos,
                    original_photos=_session.original_photos,
                    filter_name=_session.filter,
                    effects=_session.polish_applied,
                )

                # Step 3: Generate print composite
                Clock.schedule_once(lambda _: self._loading.update(
                    self.t("loading.composing")), 0)
                try:
                    from photobooth.services.print_layouts import (
                        compose_print, get_theme_branding_colors,
                    )
                    event_name = ""
                    if self.config:
                        event_name = self.config.app.event_name
                    logo_path = self.config.print_layout.logo_path if self.config else ""
                    font_path = self.theme.typography.font_file or ""
                    theme_colors = get_theme_branding_colors(self.theme)

                    composite = compose_print(
                        layout=_session.layout,
                        photos=_session.captured_photos,
                        event_name=event_name,
                        logo_path=logo_path,
                        theme_colors=theme_colors,
                        font_path=font_path,
                    )
                    _session.print_composite = composite
                    self.storage.save_print_composite(
                        session_id=_session.session_id,
                        event_id=_session.event_id,
                        layout=_session.layout,
                        composite_jpeg=composite,
                    )
                except Exception as e:
                    logger.error("Failed to generate print composite: %s", e)

                # Step 4: Upload to server
                Clock.schedule_once(lambda _: self._loading.update(
                    "Uploading...") if hasattr(self, '_loading') and self._loading else None, 0)
                try:
                    self._upload_session_photos(_session)
                except Exception as e:
                    logger.error("Photo upload failed: %s", e)

        except Exception as e:
            logger.error("Accept processing failed: %s", e)

        # Done — navigate on main thread
        Clock.schedule_once(lambda _: self._accept_done(), 0)

    def _accept_done(self) -> None:
        """Called on main thread after processing completes."""
        if hasattr(self, '_loading') and self._loading:
            # Force-remove immediately (don't animate — we're navigating away)
            self._loading.hide(remove=False)
            if self._loading.parent:
                self._loading.parent.remove_widget(self._loading)
            self._loading = None
        self.navigate_to(SCREEN_DELIVER)

    def _upload_session_photos(self, session) -> None:
        """Upload final photos to the server for the public gallery."""
        agent = getattr(self, '_agent', None)
        if not agent:
            # Try to find agent from the app
            from kivy.app import App
            app = App.get_running_app()
            agent = getattr(app, 'agent', None)

        if not agent:
            logger.debug("No agent available — skipping upload")
            return

        # Reset session token so QR code will show new session's token
        agent.last_session_token = ""

        if not self.storage or not session.session_id:
            return

        # Use the server's event ID (UUID), not the local integer
        server_event_id = agent.server_event_id or ""

        # Get all final photos for this session
        photos = self.storage.get_session_photos(session.session_id)
        upload_list = []

        for photo in photos:
            if photo.get("variant") != "final":
                continue
            file_path = self.storage.get_photo_path(photo["filename"])
            if file_path.exists():
                upload_list.append({
                    "file_path": str(file_path),
                    "event_id": server_event_id,
                    "session_id": str(session.session_id),
                    "seq": photo.get("seq", 1),
                    "variant": "final",
                })

        if upload_list:
            logger.info("Queuing %d photos for upload", len(upload_list))
            agent.upload_photos(upload_list)

    def _go_to_idle(self, _dt) -> None:
        self.navigate_to(SCREEN_IDLE)


class DeliverScreen(BaseBoothScreen):
    """Photo delivery screen with print composite preview.

    Shows the final print result with the chosen layout (single/strip/grid)
    on the left, and action buttons (QR, Send, Print, Done) on the right.
    """

    _AUTO_TIMEOUT = 45.0  # Return to idle after timeout

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_DELIVER, **kwargs)

        # Title
        self._title = Label(
            text=self.t("deliver.title"),
            font_size=self.theme.typography.title_size,
            bold=True,
            color=self.theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.94},
        )
        self.add_widget(self._title)

        # Print composite preview (left side, large)
        self._composite_image = UixImage(
            size_hint=(0.42, 0.78),
            pos_hint={"center_x": 0.27, "center_y": 0.46},
            fit_mode="contain",
        )
        self.add_widget(self._composite_image)

        # Subtle border around composite preview
        with self._composite_image.canvas.before:
            from kivy.graphics import Color, Line
            Color(1, 1, 1, 0.15)
            self._border_rect = Line(
                rectangle=(0, 0, 100, 100), width=1,
            )
        self._composite_image.bind(
            pos=self._update_border, size=self._update_border,
        )

        # Right side panel for QR + buttons
        self._right_panel = FloatLayout(
            size_hint=(0.40, 0.82),
            pos_hint={"center_x": 0.74, "center_y": 0.46},
        )
        self.add_widget(self._right_panel)

        self._timeout_event = None

    def _update_border(self, *args):
        """Keep the border rectangle in sync with the image widget."""
        self._border_rect.rectangle = (
            self._composite_image.x,
            self._composite_image.y,
            self._composite_image.width,
            self._composite_image.height,
        )

    def on_enter(self, *args) -> None:
        super().on_enter(*args)
        self._show_composite()
        self._build_right_panel()
        self._timeout_event = Clock.schedule_once(
            self._go_to_idle, self._AUTO_TIMEOUT,
        )

    def on_leave(self, *args) -> None:
        if self._timeout_event:
            self._timeout_event.cancel()
            self._timeout_event = None

    def _show_composite(self) -> None:
        """Display the print composite from the session."""
        if _session.print_composite:
            try:
                core_img = CoreImage(
                    io.BytesIO(_session.print_composite), ext="jpeg",
                )
                self._composite_image.texture = core_img.texture
            except Exception as e:
                logger.error("Failed to display composite: %s", e)

    def _build_right_panel(self) -> None:
        """Build QR code + action buttons on the right side."""
        self._right_panel.clear_widgets()

        # Small QR code at the top
        qr_image = UixImage(
            size_hint=(0.55, 0.30),
            pos_hint={"center_x": 0.5, "top": 1.0},
            fit_mode="contain",
        )
        self._right_panel.add_widget(qr_image)
        self._generate_qr(qr_image)

        # QR hint
        self._right_panel.add_widget(Label(
            text=self.t("deliver.scan_hint"),
            font_size="16sp",
            color=self.theme.colors.text_muted,
            pos_hint={"center_x": 0.5, "y": 0.64},
            size_hint=(1, 0.05),
        ))

        # Print button
        self._right_panel.add_widget(BoothButton(
            text=self.t("deliver.print_btn"),
            theme=self.theme,
            variant="secondary",
            on_press=self._trigger_print,
            size_hint=(0.85, 0.13),
            pos_hint={"center_x": 0.5, "center_y": 0.52},
        ))

        # Send to Me
        self._right_panel.add_widget(BoothButton(
            text=self.t("deliver.send_to_me"),
            theme=self.theme,
            variant="secondary",
            on_press=self._send_to_me,
            size_hint=(0.85, 0.13),
            pos_hint={"center_x": 0.5, "center_y": 0.35},
        ))

        # Done (primary CTA)
        self._right_panel.add_widget(BoothButton(
            text=self.t("deliver.done"),
            theme=self.theme,
            variant="primary",
            on_press=self._done,
            size_hint=(0.85, 0.15),
            pos_hint={"center_x": 0.5, "center_y": 0.12},
        ))

    def _generate_qr(self, qr_widget) -> None:
        """Generate a QR code pointing to the session viewer page."""
        try:
            import qrcode

            # Build URL from config
            public_url = "https://photobooth.mycreativity.nl"

            if self.config and hasattr(self.config, "server"):
                public_url = self.config.server.public_url or public_url

            # Get session token from agent (set after photo upload)
            from kivy.app import App
            app = App.get_running_app()
            agent = getattr(app, 'agent', None)

            session_token = ""
            if agent and agent.last_session_token:
                session_token = agent.last_session_token

            if session_token:
                # Direct link to this session's photos
                url = f"{public_url}/s/{session_token}"
            else:
                # Fallback: event gallery
                event_uid = ""
                if agent and agent.server_event_uid:
                    event_uid = agent.server_event_uid
                url = f"{public_url}/e/{event_uid}" if event_uid else public_url

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)

            pil_img = qr.make_image(fill_color="white", back_color="#232333")
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            buf.seek(0)
            core_img = CoreImage(buf, ext="png")
            qr_widget.texture = core_img.texture

            logger.info("QR code generated: %s", url)

        except Exception as e:
            logger.error("Failed to generate QR code: %s", e)

    def _send_to_me(self) -> None:
        """Stub: email/SMS delivery — will be implemented with backend."""
        logger.info("Send-to-me requested (not yet implemented)")

    def _trigger_print(self) -> None:
        """Trigger physical print if enabled."""
        printing_enabled = self.config.printing.enabled if self.config else False
        if printing_enabled:
            logger.info("Print triggered for session %s", _session.session_id)
        else:
            logger.info("Printing not enabled")

    def _done(self) -> None:
        """User is done — return to idle."""
        printing_auto = self.config.printing.enabled if self.config else False
        if printing_auto:
            self._trigger_print()
        self.navigate_to(SCREEN_IDLE)

    def _go_to_idle(self, _dt) -> None:
        self.navigate_to(SCREEN_IDLE)


class PrintScreen(BaseBoothScreen):
    """Print confirmation — placeholder."""

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_PRINT, **kwargs)
        self.add_widget(Label(
            text=self.t("print.sending"),
            font_size=self.theme.typography.title_size,
            color=self.theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        ))


class PincodeScreen(BaseBoothScreen):
    """PIN entry screen that guards access to the settings screen.

    Shows a 3×4 numpad on a black background. Auto-confirms when 4 digits
    are entered. Wrong PIN shows a brief error and clears. Times out to
    the idle screen after 30 s of inactivity; each touch resets the timer.
    """

    _PIN_LENGTH = 4
    _INACTIVITY_TIMEOUT = 30.0

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_PINCODE, **kwargs)
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.boxlayout import BoxLayout

        self._entered: list[str] = []

        # Opaque black background
        with self.canvas.before:
            Color(0, 0, 0, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        # Back button — ghost, top-left
        self.add_widget(BoothButton(
            text=self.t("pincode.back"),
            theme=self.theme,
            variant="ghost",
            on_press=self._go_back,
            font_size="18sp",
            size_hint=(0.12, 0.065),
            pos_hint={"x": 0.03, "top": 0.97},
        ))

        # Title
        self.add_widget(Label(
            text=self.t("pincode.title"),
            font_size="36sp",
            bold=True,
            color=(1, 1, 1, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.80},
        ))

        # Pin dot row — 4 circle characters in a BoxLayout
        dots_row = BoxLayout(
            orientation="horizontal",
            spacing=24,
            size_hint=(None, None),
            size=(224, 56),
            pos_hint={"center_x": 0.5, "center_y": 0.66},
        )
        self._dot_labels: list[Label] = []
        for _ in range(self._PIN_LENGTH):
            lbl = Label(
                text="○",
                font_size="44sp",
                color=(1, 1, 1, 0.35),
                size_hint=(1, 1),
            )
            self._dot_labels.append(lbl)
            dots_row.add_widget(lbl)
        self.add_widget(dots_row)

        # Error label
        self._error_label = Label(
            text="",
            font_size="22sp",
            color=(0.9, 0.25, 0.25, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.54},
        )
        self.add_widget(self._error_label)

        # Numpad — 3 cols × 4 rows
        grid = GridLayout(
            cols=3, rows=4, spacing=16,
            size_hint=(0.54, 0.50),
            pos_hint={"center_x": 0.5, "center_y": 0.27},
        )
        self.add_widget(grid)

        dark_text = self.theme.colors.background
        numpad_keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", ""]
        for key in numpad_keys:
            if key == "":
                grid.add_widget(Widget())
            elif key == "⌫":
                grid.add_widget(BoothButton(
                    text=key,
                    theme=self.theme,
                    variant="primary",
                    on_press=self._backspace,
                    text_color=dark_text,
                    size_hint=(1, 1),
                ))
            else:
                k = key
                grid.add_widget(BoothButton(
                    text=k,
                    theme=self.theme,
                    variant="primary",
                    on_press=lambda _k=k: self._digit(_k),
                    text_color=dark_text,
                    size_hint=(1, 1),
                ))

    # ---- layout sync --------------------------------------------------------

    def _sync_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    # ---- dot display --------------------------------------------------------

    def _update_dots(self) -> None:
        for i, lbl in enumerate(self._dot_labels):
            if i < len(self._entered):
                lbl.text = "●"
                lbl.color = (1, 1, 1, 1)
            else:
                lbl.text = "○"
                lbl.color = (1, 1, 1, 0.35)

    def _flash_error(self) -> None:
        for lbl in self._dot_labels:
            lbl.text = "●"
            lbl.color = (0.9, 0.25, 0.25, 1)

    # ---- lifecycle ----------------------------------------------------------

    def on_enter(self, *args) -> None:
        super().on_enter(*args)
        self._entered = []
        self._error_label.text = ""
        self._update_dots()
        self._start_inactivity_timer(self._INACTIVITY_TIMEOUT)

    def on_leave(self, *args) -> None:
        self._cancel_inactivity_timer()

    def on_touch_down(self, touch) -> bool:
        self._reset_inactivity_timer()
        return super().on_touch_down(touch)

    # ---- input handling -----------------------------------------------------

    def _digit(self, d: str) -> None:
        if len(self._entered) >= self._PIN_LENGTH:
            return
        self._entered.append(d)
        self._update_dots()
        self._reset_inactivity_timer()
        if len(self._entered) == self._PIN_LENGTH:
            self._check_pin()

    def _backspace(self) -> None:
        if self._entered:
            self._entered.pop()
            self._update_dots()
        self._error_label.text = ""
        self._reset_inactivity_timer()

    def _check_pin(self) -> None:
        correct = "1234"
        if self.config:
            correct = self.config.app.settings_pin
        if "".join(self._entered) == correct:
            self._entered = []
            self._update_dots()
            self.navigate_to(SCREEN_SETTINGS)
        else:
            self._error_label.text = self.t("pincode.wrong")
            self._flash_error()
            Clock.schedule_once(self._clear_error, 0.9)

    def _clear_error(self, _dt) -> None:
        self._entered = []
        self._update_dots()
        self._error_label.text = ""

    def _go_back(self) -> None:
        self.navigate_to(SCREEN_IDLE)


class SettingsScreen(BaseBoothScreen):
    """Minimal settings screen — black background, screen-filling 2×3 grid.

    Accessed via a 5s long-press from the idle screen. Three of the six grid
    blocks are populated (the gridlines themselves stay invisible):

      1. Back button.
      2. Info card for the event pushed from the admin (read from the cached
         ``event_card.json``).
      3. Restart-app button.

    The remaining blocks are intentionally empty, reserved for future use.
    Booth configuration is no longer edited here — values are still loaded
    from TOML + SQLite at startup, so the rest of the app keeps working.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(name=SCREEN_SETTINGS, **kwargs)
        from kivy.uix.gridlayout import GridLayout

        # Opaque black background — hides the live camera preview that the
        # other screens show behind the screen manager.
        with self.canvas.before:
            Color(0, 0, 0, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        # 2×3 grid of large blocks (gridlines invisible), slightly inset.
        grid = GridLayout(
            cols=3, rows=2, spacing=24, padding=12,
            size_hint=(0.9, 0.84),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self.add_widget(grid)

        # Dark text reads better than white on the opaque gold blocks
        # (unlike the idle start button, which sits over the live preview).
        dark_text = self.theme.colors.background

        # Block 1 — Back
        grid.add_widget(BoothButton(
            text=self.t("settings.back"),
            theme=self.theme,
            variant="primary",
            on_press=self._go_back,
            size_hint=(1, 1),
            text_color=dark_text,
        ))

        # Block 2 — pushed-event info card
        grid.add_widget(self._build_event_cell())

        # Block 3 — Restart
        grid.add_widget(BoothButton(
            text="Herstart app",
            theme=self.theme,
            variant="primary",
            on_press=self._restart_app,
            size_hint=(1, 1),
            text_color=dark_text,
        ))

        # Blocks 4–6 — intentionally empty (reserved for future controls).
        for _ in range(3):
            grid.add_widget(Widget())

    # ---- layout helpers ---------------------------------------------------

    def _sync_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _build_event_cell(self) -> FloatLayout:
        """Inverted event card: black fill with yellow border."""
        cell = FloatLayout(size_hint=(1, 1))

        accent = self.theme.colors.accent

        with cell.canvas.before:
            # Glow (accent at low alpha, slightly larger)
            Color(*accent[:3], 0.20)
            self._card_glow = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[22])
            # Border ring (accent fill)
            Color(*accent[:3], 1.0)
            self._card_border = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[16])
            # Black fill inset by 3px
            Color(0, 0, 0, 1)
            self._card_rect = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[14])

        def _sync(*_a):
            inset = 3
            self._card_glow.pos = (cell.x - 4, cell.y - 4)
            self._card_glow.size = (cell.width + 8, cell.height + 8)
            self._card_border.pos = cell.pos
            self._card_border.size = cell.size
            self._card_rect.pos = (cell.x + inset, cell.y + inset)
            self._card_rect.size = (cell.width - inset * 2, cell.height - inset * 2)
        cell.bind(pos=_sync, size=_sync)

        cell.add_widget(Label(
            text=self.t("event.current"),
            font_size=self.theme.typography.body_size,
            color=(*accent[:3], 0.75),
            halign="center", valign="middle",
            size_hint=(0.9, 0.16),
            pos_hint={"center_x": 0.5, "center_y": 0.85},
        ))

        self._event_name_lbl = Label(
            text="",
            font_size=self.theme.typography.subtitle_size,
            bold=True, color=(1, 1, 1, 1),
            halign="center", valign="middle",
            size_hint=(0.9, 0.28),
            pos_hint={"center_x": 0.5, "center_y": 0.60},
        )
        self._event_name_lbl.bind(size=self._event_name_lbl.setter("text_size"))
        cell.add_widget(self._event_name_lbl)

        self._event_meta_lbl = Label(
            text="",
            font_size="16sp",
            color=(1, 1, 1, 0.75),
            halign="center", valign="top",
            size_hint=(0.9, 0.38),
            pos_hint={"center_x": 0.5, "center_y": 0.26},
        )
        self._event_meta_lbl.bind(size=self._event_meta_lbl.setter("text_size"))
        cell.add_widget(self._event_meta_lbl)

        return cell

    # ---- lifecycle --------------------------------------------------------

    _INACTIVITY_TIMEOUT = 30.0

    def on_enter(self, *args) -> None:
        super().on_enter(*args)
        self._refresh_event_card()
        self._start_inactivity_timer(self._INACTIVITY_TIMEOUT)

    def on_leave(self, *args) -> None:
        self._cancel_inactivity_timer()

    def on_touch_down(self, touch) -> bool:
        self._reset_inactivity_timer()
        return super().on_touch_down(touch)

    def _refresh_event_card(self) -> None:
        """Show the event pushed from the admin (cached in event_card.json)."""
        card = read_pushed_event()

        if card and card.get("event_name"):
            self._event_name_lbl.text = card.get("event_name", "")
            meta = []
            if card.get("display_date"):
                meta.append(str(card["display_date"]))
            if card.get("event_uid"):
                meta.append("ID: " + str(card["event_uid"]))
            self._event_meta_lbl.text = "\n".join(meta)
        else:
            self._event_name_lbl.text = self.t("event.no_event")
            self._event_meta_lbl.text = ""

    # ---- actions ----------------------------------------------------------

    def _do_restart(self, _dt) -> None:
        """Restart the Kivy app — cleans up LED DMA before exec."""
        import sys
        import os

        logger.info("Restarting application")

        from kivy.app import App
        app = App.get_running_app()
        if app:
            # Explicitly release LED strip DMA channel before restart
            # (on_stop does shutdown but rpi_ws281x needs _cleanup to free DMA)
            led = getattr(app, '_led', None)
            if led and led.available and led._strip:
                try:
                    led.shutdown()
                    led._strip._cleanup()
                    logger.info("LED strip DMA released")
                except Exception as e:
                    logger.warning("LED cleanup error: %s", e)

            app.stop()

        # Re-exec the process to get a clean restart
        os.execv(sys.executable, [sys.executable, "-m", "photobooth"])

    def _restart_app(self) -> None:
        """Manual restart from the settings button."""
        logger.info("Manual restart requested from settings")
        Clock.schedule_once(self._do_restart, 0.2)

    def _go_back(self) -> None:
        """Navigate back — to idle if an event is active, else event-required."""
        if self.storage:
            active = self.storage.get_active_event()
            if active:
                _session.event_id = active["id"]
                self.navigate_to(SCREEN_IDLE)
                return
        # No active event — go to the event-required screen.
        self.navigate_to(SCREEN_EVENT_REQUIRED)


# ---------------------------------------------------------------------------
# Screen registry & builder
# ---------------------------------------------------------------------------

SCREEN_REGISTRY: dict[str, type[BaseBoothScreen]] = {
    SCREEN_SPLASH: SplashScreen,
    SCREEN_EVENT_REQUIRED: EventRequiredScreen,
    SCREEN_IDLE: IdleScreen,
    SCREEN_LAYOUT: LayoutScreen,
    SCREEN_FILTER: FilterScreen,
    SCREEN_COUNTDOWN: CountdownScreen,
    SCREEN_CAPTURE: CaptureScreen,
    SCREEN_REVIEW: ReviewScreen,
    SCREEN_DELIVER: DeliverScreen,
    SCREEN_PRINT: PrintScreen,
    SCREEN_PINCODE: PincodeScreen,
    SCREEN_SETTINGS: SettingsScreen,
}


def build_screen_manager(
    t: Translations,
    theme: ThemeData,
    video_path: str | None = None,
    camera: CameraService | None = None,
    storage: StorageService | None = None,
    config: BoothConfig | None = None,
    led: LedService | None = None,
) -> FloatLayout:
    """Construct the root widget: preview + overlay + screen manager."""
    root = FloatLayout()

    preview_fps = config.camera.preview_fps if config else 15

    # Layer 1: live camera preview / video
    preview_layer = LivePreviewLayer(
        bg_color=theme.colors.background,
        video_path=video_path,
        camera=camera,
        preview_fps=preview_fps,
        size_hint=(1, 1),
    )
    root.add_widget(preview_layer)

    # Layer 2: shared semi-transparent overlay
    overlay = OverlayLayer(
        overlay_color=theme.colors.overlay,
        size_hint=(1, 1),
    )
    root.add_widget(overlay)

    # Layer 3: screen manager
    sm = ScreenManager(transition=NoTransition())

    shared = dict(
        t=t,
        theme=theme,
        camera=camera,
        storage=storage,
        config=config,
        preview_layer=preview_layer,
        led=led,
    )

    all_screens = list(SCREEN_FLOW) + [SCREEN_PINCODE, SCREEN_SETTINGS]
    for name in all_screens:
        screen_cls = SCREEN_REGISTRY[name]
        sm.add_widget(screen_cls(**shared))
    sm.current = SCREEN_SPLASH

    root.add_widget(sm)

    return root
