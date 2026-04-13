"""LED strip service for photobooth ambient & flash lighting.

Controls an SK6812 RGBW LED strip (80 LEDs on GPIO18 via PWM).
All animations run in a background thread so they don't block the UI.
Every transition between states is smooth (eased fade).

Requires root privileges for PWM access (app runs via sudo -E in kiosk).
Fails gracefully if the LED hardware is not available.
"""

from __future__ import annotations

import logging
import math
import random
import threading
from dataclasses import dataclass
from typing import Tuple

logger = logging.getLogger(__name__)

try:
    from rpi_ws281x import PixelStrip, Color, ws
    _HAS_LED = True
except ImportError:
    _HAS_LED = False
    logger.info("rpi_ws281x not installed — LED service disabled")


@dataclass
class LedConfig:
    """LED strip configuration."""

    enabled: bool = True
    led_count: int = 80
    gpio_pin: int = 18
    brightness: int = 80
    flash_brightness: int = 255
    dma_channel: int = 10
    freq_hz: int = 800000


# ---- Colour helpers ----

def _color(r: int, g: int, b: int, w: int = 0) -> int:
    if not _HAS_LED:
        return 0
    return Color(r, g, b, w)


def _ease(t: float) -> float:
    """Smooth ease-in-out (cosine). t: 0..1 → 0..1."""
    return (1 - math.cos(t * math.pi)) / 2


def _lerp(a: Tuple[int, ...], b: Tuple[int, ...], t: float) -> Tuple[int, ...]:
    """Interpolate between two RGBW colour tuples."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(4))


# ---- Pre-defined colours (R, G, B, W) ----
OFF = (0, 0, 0, 0)
WARM_YELLOW = (80, 50, 0, 25)
WARM_YELLOW_DIM = (35, 22, 0, 12)
WHITE_FLASH = (200, 200, 200, 255)
COUNTDOWN_GREEN = (0, 180, 0, 0)
COUNTDOWN_YELLOW = (200, 150, 0, 0)
COUNTDOWN_RED = (255, 30, 0, 0)
CELEBRATE_GOLD = (255, 180, 0, 30)
CELEBRATE_PINK = (255, 50, 100, 0)
CELEBRATE_BLUE = (30, 80, 255, 0)
CELEBRATE_GREEN = (0, 255, 80, 0)


class LedService:
    """Thread-safe LED strip controller with smooth transitions."""

    def __init__(self, config: LedConfig | None = None) -> None:
        self._cfg = config or LedConfig()
        self._strip = None
        self._lock = threading.Lock()
        self._anim_thread: threading.Thread | None = None
        self._anim_stop = threading.Event()
        self._available = False
        self._current = OFF

        if not self._cfg.enabled or not _HAS_LED:
            logger.info("LED service disabled (enabled=%s, lib=%s)",
                        self._cfg.enabled, _HAS_LED)
            return

        try:
            self._strip = PixelStrip(
                self._cfg.led_count, self._cfg.gpio_pin,
                self._cfg.freq_hz, self._cfg.dma_channel,
                False, self._cfg.brightness, 0,
                ws.SK6812_STRIP_GRBW,
            )
            self._strip.begin()
            # Clear any leftover LED state from previous runs
            for i in range(self._cfg.led_count):
                self._strip.setPixelColor(i, 0)
            self._strip.show()
            self._available = True
            logger.info("LED service ready: %d LEDs on GPIO%d",
                        self._cfg.led_count, self._cfg.gpio_pin)
        except Exception as e:
            logger.warning("LED init failed (need root?): %s", e)

    @property
    def available(self) -> bool:
        return self._available

    # ---- Public API ----

    def mood(self) -> None:
        self._stop_anim()
        self._start_anim(self._mood_loop)

    def countdown(self, remaining: int, total: int) -> None:
        if not self._available:
            return
        self._stop_anim()
        ratio = remaining / max(total, 1)
        target = COUNTDOWN_GREEN if ratio > 0.5 else (
            COUNTDOWN_YELLOW if ratio > 0.2 else COUNTDOWN_RED)
        self._fade_to(target, self._cfg.brightness, 15)

    def pre_capture(self) -> None:
        self._stop_anim()
        self._fade_to(WHITE_FLASH, self._cfg.flash_brightness, 20)

    def flash(self) -> None:
        self._stop_anim()
        self._set_all(WHITE_FLASH, self._cfg.flash_brightness)

    def celebrate(self) -> None:
        self._stop_anim()
        self._start_anim(self._celebrate_loop)

    def off(self) -> None:
        self._stop_anim()
        self._fade_to(OFF, 0, 30)

    def shutdown(self) -> None:
        self._stop_anim()
        self._set_all(OFF, 0)
        logger.info("LED service shut down")

    # ---- Low-level ----

    def _set_all(self, color, brightness=None):
        if not self._available or not self._strip:
            return
        with self._lock:
            if brightness is not None:
                self._strip.setBrightness(brightness)
            c = _color(*color)
            for i in range(self._cfg.led_count):
                self._strip.setPixelColor(i, c)
            self._strip.show()
        self._current = color

    def _set_per_led(self, colors, brightness=None):
        if not self._available or not self._strip:
            return
        with self._lock:
            if brightness is not None:
                self._strip.setBrightness(brightness)
            for i, col in enumerate(colors):
                if i >= self._cfg.led_count:
                    break
                self._strip.setPixelColor(i, _color(*col))
            self._strip.show()

    def _fade_to(self, target, brightness=None, frames=30):
        """Eased fade from current colour to target."""
        start = self._current
        for f in range(frames + 1):
            if self._anim_stop.is_set():
                break
            t = _ease(f / frames)
            self._set_all(_lerp(start, target, t), brightness)
            if f < frames:
                self._anim_stop.wait(0.025)
        self._current = target

    def _stop_anim(self):
        if self._anim_thread and self._anim_thread.is_alive():
            self._anim_stop.set()
            self._anim_thread.join(timeout=2)
        self._anim_stop.clear()

    def _start_anim(self, fn):
        if not self._available:
            return
        def _safe_run():
            try:
                fn()
            except Exception:
                logger.exception("LED animation thread crashed")
        self._anim_thread = threading.Thread(target=_safe_run, daemon=True)
        self._anim_thread.start()

    # ---- Mood animation ----

    def _mood_loop(self):
        logger.info("LED mood loop started")
        n = self._cfg.led_count
        base, dim, br = WARM_YELLOW, WARM_YELLOW_DIM, self._cfg.brightness

        def _solid():
            self._set_all(base, br)
            logger.debug("LED solid yellow set")

        def _fade(a, b, frames=50):
            for f in range(frames + 1):
                if self._anim_stop.is_set():
                    return False
                self._set_all(_lerp(a, b, _ease(f / frames)), br)
                self._anim_stop.wait(0.028)
            return True

        def _chase():
            if not _fade(base, dim):
                return
            for step in range(n * 2):
                if self._anim_stop.is_set():
                    return
                center = step % n
                cols = []
                for i in range(n):
                    d = min(abs(i - center), n - abs(i - center))
                    if d < 8:
                        cols.append(_lerp(dim, base, math.cos(d / 8 * math.pi / 2)))
                    else:
                        cols.append(dim)
                self._set_per_led(cols, br)
                self._anim_stop.wait(0.022)
            _fade(dim, base)

        def _breathe():
            for _ in range(2):
                if not _fade(base, dim, 55):
                    return
                if not _fade(dim, base, 55):
                    return

        def _sparkle():
            bright = tuple(min(255, int(base[c] * 2.5)) for c in range(4))
            for _ in range(100):
                if self._anim_stop.is_set():
                    return
                cols = [base] * n
                for _ in range(random.randint(3, 6)):
                    cols[random.randint(0, n - 1)] = bright
                self._set_per_led(cols, br)
                self._anim_stop.wait(0.06)

        def _wave():
            if not _fade(base, dim, 40):
                return
            for step in range(n * 3):
                if self._anim_stop.is_set():
                    return
                cols = []
                for i in range(n):
                    w = (math.sin((i - step) * math.pi * 2 / n) + 1) / 2
                    cols.append(_lerp(dim, base, w))
                self._set_per_led(cols, br)
                self._anim_stop.wait(0.028)
            _fade(dim, base, 40)

        def _converge():
            if not _fade(base, dim):
                return
            half = n // 2
            for step in range(half + 6):
                if self._anim_stop.is_set():
                    return
                cols = [dim] * n
                for g in range(6):
                    glow = math.cos(g / 6 * math.pi / 2)
                    bl = _lerp(dim, base, glow)
                    idx = step - g
                    if 0 <= idx < n:
                        cols[idx] = bl
                    idx2 = (n - 1) - step + g
                    if 0 <= idx2 < n:
                        cols[idx2] = bl
                self._set_per_led(cols, br)
                self._anim_stop.wait(0.022)
            bright = tuple(min(255, int(base[c] * 2)) for c in range(4))
            _fade(dim, bright, 15)
            _fade(bright, base, 40)

        scenes = [_chase, _breathe, _sparkle, _wave, _converge]
        _solid()
        while not self._anim_stop.is_set():
            if self._anim_stop.wait(random.uniform(8, 14)):
                return
            random.choice(scenes)()
            _solid()

    # ---- Celebrate animation ----

    def _celebrate_loop(self):
        colors = [CELEBRATE_GOLD, CELEBRATE_PINK, CELEBRATE_BLUE, CELEBRATE_GREEN]
        n, br = self._cfg.led_count, self._cfg.brightness

        start = self._current
        for f in range(20):
            if self._anim_stop.is_set():
                return
            self._set_all(_lerp(start, colors[0], _ease(f / 20)), br)
            self._anim_stop.wait(0.025)

        offset = 0
        while not self._anim_stop.is_set():
            cols = []
            for i in range(n):
                pos = ((i + offset) % n) / n * len(colors)
                idx = int(pos) % len(colors)
                frac = pos - int(pos)
                nxt = (idx + 1) % len(colors)
                cols.append(_lerp(colors[idx], colors[nxt], _ease(frac)))
            self._set_per_led(cols, br)
            offset += 1
            self._anim_stop.wait(0.05)
