"""Canon DSLR camera service via gphoto2.

Provides ``GPhoto2CameraService`` for tethered DSLR control.
Supports live preview, full-resolution capture, and runtime
adjustment of ISO, aperture, and shutter speed.

Includes an auto-exposure calibration algorithm that analyses
preview frame brightness and iteratively adjusts camera settings
to achieve optimal exposure — ideal for photobooth setups where
lighting is fixed and needs to be calibrated once.

Requires:
    - libgphoto2 system library
    - python-gphoto2 package (``pip install gphoto2``)
    - Camera set to Manual (M) mode on the physical dial
"""

from __future__ import annotations

import io
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy import — gphoto2 may not be installed on all systems
_gp = None


def _ensure_gphoto2():
    """Import gphoto2 on first use."""
    global _gp
    if _gp is None:
        try:
            import gphoto2 as gp
            _gp = gp
        except ImportError as e:
            raise ImportError(
                "python-gphoto2 is not installed. "
                "Install with: pip install gphoto2"
            ) from e
    return _gp


# ---------------------------------------------------------------------------
# Auto-exposure calibration
# ---------------------------------------------------------------------------

@dataclass
class ExposureResult:
    """Result of an auto-exposure calibration run."""
    iso: str
    aperture: str
    shutter_speed: str
    brightness: float      # Final measured brightness (0–255)
    iterations: int         # How many adjustment rounds
    success: bool           # Whether target was reached


# Standard ISO and shutter speed ladders for Canon EOS
_ISO_LADDER = ["100", "200", "400", "800", "1600", "3200", "6400"]
_SHUTTER_LADDER = [
    "1/8", "1/15", "1/30", "1/60", "1/125", "1/250", "1/500", "1/1000", "1/2000",
]

# The LED flash adds ~1.5 stops of light on top of ambient.
# We calibrate for slightly underexposed preview so the final
# photo (with flash) lands around 128.
_FLASH_COMPENSATION = 30  # points to subtract from target 128


def _shutter_to_float(s: str) -> float:
    """Convert a shutter speed string to a float (seconds)."""
    if "/" in s:
        parts = s.split("/")
        return float(parts[0]) / float(parts[1])
    return float(s)


# ---------------------------------------------------------------------------
# GPhoto2 Camera Service
# ---------------------------------------------------------------------------

class GPhoto2CameraService:
    """Tethered DSLR control via libgphoto2.

    Implements the same ``CameraService`` protocol as
    ``WebcamCameraService``, so the app can swap between them
    transparently.

    The live preview loop runs in a background thread, calling
    ``camera.capture_preview()`` at the target FPS and pushing
    JPEG frames into a bounded queue.
    """

    name = "Canon DSLR"

    def __init__(
        self,
        preview_fps: int = 12,
        capture_quality: int = 95,
        iso: str = "auto",
        aperture: str = "",
        shutter_speed: str = "auto",
        **_kwargs,
    ) -> None:
        self._preview_fps = preview_fps
        self._capture_quality = capture_quality
        self._initial_iso = iso
        self._initial_aperture = aperture
        self._initial_shutter = shutter_speed

        self._camera = None
        self._context = None
        self._previewing = False
        self._ready = False
        self._preview_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._frame_queue: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self._lock = threading.Lock()
        self._preview_filter: str = "classic"

    @property
    def is_previewing(self) -> bool:
        return self._previewing

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def preview_filter(self) -> str:
        return self._preview_filter

    @preview_filter.setter
    def preview_filter(self, value: str) -> None:
        self._preview_filter = value

    # ----- lifecycle -------------------------------------------------------

    def warm_up(self) -> None:
        """Pre-connect to the camera in a background thread."""
        if self._ready or self._camera is not None:
            return
        threading.Thread(
            target=self._do_warm_up,
            name="gphoto2-warmup",
            daemon=True,
        ).start()

    def _do_warm_up(self) -> None:
        """Background: connect to the camera."""
        try:
            self._ensure_camera()
            self._apply_initial_settings()
            self._ready = True
            logger.info("Canon DSLR warmed up and ready")
        except Exception as e:
            logger.error("DSLR warm-up failed: %s", e)

    def _ensure_camera(self) -> None:
        """Open a connection to the camera. Thread-safe."""
        if self._camera is not None:
            return

        # On macOS, kill the PTP daemon that grabs the camera
        self._kill_ptp_daemon()

        gp = _ensure_gphoto2()
        self._context = gp.Context()
        self._camera = gp.Camera()
        self._camera.init(self._context)

        # Log camera info
        abilities = self._camera.get_abilities()
        logger.info("Connected to: %s", abilities.model)

    @staticmethod
    def _kill_ptp_daemon() -> None:
        """Kill macOS PTPCamera process that blocks gphoto2 access.

        On macOS, the system automatically starts a PTP daemon when a
        camera is connected via USB. This daemon claims exclusive access,
        preventing gphoto2 from communicating with the camera.
        """
        import platform
        if platform.system() != "Darwin":
            return

        import subprocess
        try:
            subprocess.run(
                ["killall", "PTPCamera"],
                capture_output=True, timeout=5,
            )
            logger.info("Killed macOS PTPCamera daemon")
        except Exception:
            pass  # No PTPCamera running — that's fine

    def _apply_initial_settings(self) -> None:
        """Apply ISO/aperture/shutter from config (if not 'auto')."""
        if self._initial_iso and self._initial_iso != "auto":
            self._set_config("iso", self._initial_iso)
        if self._initial_aperture:
            self._set_config("aperture", self._initial_aperture)
        if self._initial_shutter and self._initial_shutter != "auto":
            self._set_config("shutterspeed", self._initial_shutter)

    # ----- preview ---------------------------------------------------------

    def start_preview(self) -> None:
        """Start the background live view loop."""
        if self._previewing:
            return

        self._stop_event.clear()
        self._previewing = True

        self._preview_thread = threading.Thread(
            target=self._preview_loop,
            name="gphoto2-preview",
            daemon=True,
        )
        self._preview_thread.start()
        logger.info("DSLR preview starting (target %d fps)", self._preview_fps)

    def stop_preview(self) -> None:
        """Stop the live view loop."""
        if not self._previewing:
            return

        self._stop_event.set()
        self._previewing = False

        if self._preview_thread:
            self._preview_thread.join(timeout=3.0)
            self._preview_thread = None

        # Drain queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("DSLR preview stopped")

    def get_preview_frame(self) -> bytes | None:
        """Return the most recent preview frame."""
        frame = None
        while True:
            try:
                frame = self._frame_queue.get_nowait()
            except queue.Empty:
                break
        return frame

    def _preview_loop(self) -> None:
        """Background: continuously capture preview frames."""
        gp = _ensure_gphoto2()

        try:
            self._ensure_camera()
        except Exception as e:
            logger.error("Failed to connect to DSLR: %s", e)
            self._previewing = False
            return

        interval = 1.0 / self._preview_fps

        while not self._stop_event.is_set():
            start = time.monotonic()

            try:
                with self._lock:
                    camera_file = self._camera.capture_preview()

                # Get JPEG data from the camera file
                file_data = camera_file.get_data_and_size()
                jpeg_bytes = bytes(file_data)

                # Boost preview brightness — the viewfinder feed is darker
                # than the final capture because it doesn't include flash.
                jpeg_bytes = self._boost_preview_brightness(jpeg_bytes)

                # Apply filter if active
                active_filter = self._preview_filter
                if active_filter not in ("none", "classic", ""):
                    jpeg_bytes = self._apply_filter(jpeg_bytes, active_filter)

                # Push to queue (drop old frames if full)
                try:
                    self._frame_queue.put_nowait(jpeg_bytes)
                except queue.Full:
                    try:
                        self._frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._frame_queue.put_nowait(jpeg_bytes)
                    except queue.Full:
                        pass

            except Exception as e:
                # Camera may briefly fail during capture — log and retry
                logger.debug("Preview frame error: %s", e)
                time.sleep(0.1)

            elapsed = time.monotonic() - start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    # ----- pre-capture preparation ------------------------------------------

    def trigger_autofocus(self) -> bool:
        """Trigger a single autofocus cycle on the camera.

        Uses the Canon-specific 'autofocusdrive' control to force AF.
        Returns True if the command was sent successfully.
        """
        gp = _ensure_gphoto2()
        with self._lock:
            try:
                self._ensure_camera()
                config = self._camera.get_config(self._context)
                af_widget = config.get_child_by_name("autofocusdrive")
                af_widget.set_value(1)
                self._camera.set_config(config, self._context)
                logger.info("Autofocus triggered")
                return True
            except Exception as e:
                logger.warning("Autofocus trigger failed: %s", e)
                return False

    def prepare_for_capture(self) -> None:
        """Trigger autofocus before capture.

        Call this at the start of the countdown so the lens locks
        focus at the correct distance (users step back from the
        touchscreen).  Exposure is handled by the camera's own
        auto mode.
        """
        self.trigger_autofocus()

    # ----- capture ---------------------------------------------------------

    def capture_photo(self) -> bytes:
        """Capture a full-resolution photo and return JPEG bytes.

        The camera saves the image to its internal storage, then we
        download it and return the raw bytes.
        """
        gp = _ensure_gphoto2()

        with self._lock:
            self._ensure_camera()

            # Capture — this triggers the shutter
            file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
            logger.info(
                "DSLR captured: %s/%s", file_path.folder, file_path.name,
            )

            # Download the file from the camera
            camera_file = self._camera.file_get(
                file_path.folder, file_path.name,
                gp.GP_FILE_TYPE_NORMAL,
            )
            file_data = camera_file.get_data_and_size()
            jpeg_bytes = bytes(file_data)

            # Delete from camera to save space
            try:
                self._camera.file_delete(file_path.folder, file_path.name)
            except Exception:
                pass  # Non-critical — camera card just fills up slowly

            logger.info(
                "Photo downloaded: %d bytes", len(jpeg_bytes),
            )

            return jpeg_bytes

    # ----- camera settings -------------------------------------------------

    def get_config_value(self, name: str) -> str:
        """Get the current value of a camera setting.

        Common names: "iso", "aperture", "shutterspeed",
        "imageformat", "whitebalance".
        """
        gp = _ensure_gphoto2()
        with self._lock:
            self._ensure_camera()
            config = self._camera.get_config(self._context)
            try:
                widget = config.get_child_by_name(name)
                return widget.get_value()
            except Exception:
                return ""

    def get_config_choices(self, name: str) -> list[str]:
        """Get available choices for a camera setting."""
        gp = _ensure_gphoto2()
        with self._lock:
            self._ensure_camera()
            config = self._camera.get_config(self._context)
            try:
                widget = config.get_child_by_name(name)
                return [widget.get_choice(i) for i in range(widget.count_choices())]
            except Exception:
                return []

    def set_config_value(self, name: str, value: str) -> bool:
        """Set a camera setting. Returns True on success."""
        return self._set_config(name, value)

    def _set_config(self, name: str, value: str) -> bool:
        """Internal: set a camera config value under lock."""
        gp = _ensure_gphoto2()
        with self._lock:
            try:
                self._ensure_camera()
                config = self._camera.get_config(self._context)
                widget = config.get_child_by_name(name)
                widget.set_value(value)
                self._camera.set_config(config, self._context)
                logger.info("DSLR config: %s = %s", name, value)
                return True
            except Exception as e:
                logger.warning("Failed to set %s = %s: %s", name, value, e)
                return False

    def list_settings(self) -> dict[str, dict[str, Any]]:
        """Return a dict of key camera settings with current values and choices."""
        settings = {}
        for name in ("iso", "aperture", "shutterspeed", "imageformat", "whitebalance"):
            value = self.get_config_value(name)
            choices = self.get_config_choices(name)
            if value or choices:
                settings[name] = {"value": value, "choices": choices}
        return settings

    # ----- auto-exposure calibration ---------------------------------------

    def auto_calibrate_exposure(
        self,
        target_brightness: float = 128.0,
        tolerance: float = 15.0,
        max_iterations: int = 10,
    ) -> ExposureResult:
        """Automatically find optimal ISO and shutter speed.

        Analyses preview frames and iteratively adjusts settings until
        the average frame brightness matches the target. Aperture is
        left unchanged (depth of field is a deliberate choice).

        Args:
            target_brightness: Target average luminance (0–255). Default 128.
            tolerance: Acceptable deviation from target. Default ±15.
            max_iterations: Max adjustment rounds. Default 10.

        Returns:
            ExposureResult with the final settings and status.
        """
        logger.info(
            "Auto-calibrate: target=%.0f ±%.0f, max %d iterations",
            target_brightness, tolerance, max_iterations,
        )

        # Get available ISO and shutter values from the camera
        iso_choices = self.get_config_choices("iso")
        shutter_choices = self.get_config_choices("shutterspeed")

        # Filter to usable values (numeric ISOs, fractional shutters)
        iso_ladder = [v for v in _ISO_LADDER if v in iso_choices] or ["400"]
        shutter_ladder = [v for v in _SHUTTER_LADDER if v in shutter_choices] or ["1/125"]

        # Start at mid-range
        iso_idx = len(iso_ladder) // 2
        shutter_idx = len(shutter_ladder) // 2

        self._set_config("iso", iso_ladder[iso_idx])
        self._set_config("shutterspeed", shutter_ladder[shutter_idx])
        time.sleep(0.3)  # Let camera settle

        brightness = 0.0
        for iteration in range(max_iterations):
            brightness = self._measure_brightness()
            logger.info(
                "Calibrate iter %d: brightness=%.1f (target=%.1f), "
                "ISO=%s, shutter=%s",
                iteration + 1, brightness, target_brightness,
                iso_ladder[iso_idx], shutter_ladder[shutter_idx],
            )

            error = brightness - target_brightness

            if abs(error) <= tolerance:
                # We're within acceptable range
                break

            if error < 0:
                # Too dark — try higher ISO first, then slower shutter
                if iso_idx < len(iso_ladder) - 1:
                    iso_idx += 1
                    self._set_config("iso", iso_ladder[iso_idx])
                elif shutter_idx > 0:
                    shutter_idx -= 1
                    self._set_config("shutterspeed", shutter_ladder[shutter_idx])
                else:
                    break  # Can't go brighter
            else:
                # Too bright — try lower ISO first, then faster shutter
                if iso_idx > 0:
                    iso_idx -= 1
                    self._set_config("iso", iso_ladder[iso_idx])
                elif shutter_idx < len(shutter_ladder) - 1:
                    shutter_idx += 1
                    self._set_config("shutterspeed", shutter_ladder[shutter_idx])
                else:
                    break  # Can't go darker

            time.sleep(0.3)  # Let camera adapt

        current_aperture = self.get_config_value("aperture") or "?"

        result = ExposureResult(
            iso=iso_ladder[iso_idx],
            aperture=current_aperture,
            shutter_speed=shutter_ladder[shutter_idx],
            brightness=brightness,
            iterations=iteration + 1,
            success=abs(brightness - target_brightness) <= tolerance,
        )

        logger.info(
            "Auto-calibrate %s: ISO %s, f/%s, %s (brightness=%.1f, %d iters)",
            "✓" if result.success else "✗",
            result.iso, result.aperture, result.shutter_speed,
            result.brightness, result.iterations,
        )

        return result

    def _measure_brightness(self) -> float:
        """Capture a preview frame and return center-weighted brightness.

        Uses the center 50% of the frame for metering since faces
        are typically centered in a photobooth.
        """
        gp = _ensure_gphoto2()
        with self._lock:
            try:
                camera_file = self._camera.capture_preview()
                file_data = camera_file.get_data_and_size()
                jpeg_bytes = bytes(file_data)

                img = Image.open(io.BytesIO(jpeg_bytes)).convert("L")
                arr = np.array(img)
                h, w = arr.shape
                # Center-weighted: use middle 50% of the frame
                y1, y2 = h // 4, h * 3 // 4
                x1, x2 = w // 4, w * 3 // 4
                center = arr[y1:y2, x1:x2]
                return float(center.mean())
            except Exception as e:
                logger.warning("Brightness measurement failed: %s", e)
                return 128.0  # Fallback — neutral

    # ----- preview brightness boost -----------------------------------------

    # Pre-computed gamma lookup table for brightness boost.
    # Gamma < 1.0 = brighter; 0.7 ≈ +1 stop of light.
    _PREVIEW_GAMMA = 0.7
    _GAMMA_LUT = None

    @classmethod
    def _boost_preview_brightness(cls, jpeg_bytes: bytes) -> bytes:
        """Brighten the preview frame using gamma correction.

        The viewfinder feed from most DSLRs is darker than the actual
        capture because it doesn't account for the LED flash. Applying
        a gamma curve lifts the preview to better match the final result.
        """
        try:
            import cv2
            nparr = np.frombuffer(jpeg_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return jpeg_bytes

            # Build LUT once
            if cls._GAMMA_LUT is None:
                inv_gamma = 1.0 / cls._PREVIEW_GAMMA
                cls._GAMMA_LUT = np.array([
                    ((i / 255.0) ** inv_gamma) * 255
                    for i in range(256)
                ], dtype=np.uint8)

            frame = cv2.LUT(frame, cls._GAMMA_LUT)

            success, buffer = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85],
            )
            if success:
                return bytes(buffer)
        except Exception:
            pass
        return jpeg_bytes

    # ----- filter support --------------------------------------------------

    @classmethod
    def _apply_filter(cls, jpeg_bytes: bytes, filter_name: str) -> bytes:
        """Apply a LUT filter to JPEG preview data.

        Uses the same LUT registry as the webcam backend for
        consistent filter rendering.
        """
        try:
            import cv2
            nparr = np.frombuffer(jpeg_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return jpeg_bytes

            from photobooth.services.processing import get_lut_registry
            registry = get_lut_registry()
            if registry.has_lut(filter_name):
                frame = registry.apply_cv2(frame, filter_name)

            success, buffer = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85],
            )
            if success:
                return bytes(buffer)
        except Exception:
            pass
        return jpeg_bytes

    # ----- cleanup ---------------------------------------------------------

    def release(self) -> None:
        """Disconnect from the camera."""
        self.stop_preview()
        with self._lock:
            if self._camera is not None:
                try:
                    self._camera.exit(self._context)
                except Exception:
                    pass
                self._camera = None
                self._context = None
                self._ready = False
                logger.info("DSLR disconnected")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def list_gphoto2_cameras() -> list[dict]:
    """Detect connected gphoto2-compatible cameras.

    Returns a list of dicts with ``model`` and ``port`` keys.
    """
    try:
        gp = _ensure_gphoto2()
    except ImportError:
        return []

    try:
        cameras = gp.Camera.autodetect()
        result = []
        for name, port in cameras:
            result.append({"model": name, "port": port})
            logger.info("Found DSLR: %s at %s", name, port)
        return result
    except Exception:
        return []
