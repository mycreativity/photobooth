"""Camera service abstraction.

Defines the ``CameraService`` protocol and provides concrete implementations:

- ``StubCameraService``: Returns synthetic frames for development/testing.
- ``WebcamCameraService``: Uses OpenCV to capture from a USB/built-in webcam.
- ``GPhoto2CameraService`` (future): Wraps python-gphoto2 for DSLR control.

The protocol-based design lets the app, tests, and different deployment
targets swap camera backends cleanly via the config ``camera.backend`` key.
"""

from __future__ import annotations

import io
import logging
import os
import queue
import threading
import time
from typing import Protocol, runtime_checkable

from PIL import Image

logger = logging.getLogger(__name__)


@runtime_checkable
class CameraService(Protocol):
    """Interface that all camera backends must implement."""

    @property
    def name(self) -> str:
        """Human-readable name for this camera backend."""
        ...

    def start_preview(self) -> None:
        """Begin the live preview capture loop (background thread)."""
        ...

    def stop_preview(self) -> None:
        """Stop the live preview capture loop."""
        ...

    def capture_photo(self) -> bytes:
        """Take a full-resolution photo and return it as JPEG bytes."""
        ...

    def get_preview_frame(self) -> bytes | None:
        """Return the latest preview frame as JPEG bytes, or None."""
        ...

    @property
    def is_previewing(self) -> bool:
        """Whether the preview loop is currently active."""
        ...


# ---------------------------------------------------------------------------
# Stub implementation (development / testing)
# ---------------------------------------------------------------------------

class StubCameraService:
    """Fake camera that generates solid-colour frames for development.

    This lets you run and test the full UI pipeline on any machine without
    a camera connected.
    """

    name = "Stub Camera"

    def __init__(self, frame_width: int = 640, frame_height: int = 480) -> None:
        self._width = frame_width
        self._height = frame_height
        self._previewing = False

    def start_preview(self) -> None:
        self._previewing = True

    def stop_preview(self) -> None:
        self._previewing = False

    def capture_photo(self) -> bytes:
        """Return a synthetic JPEG image."""
        return self._generate_frame(color=(80, 120, 200))

    def get_preview_frame(self) -> bytes | None:
        if not self._previewing:
            return None
        return self._generate_frame(color=(40, 40, 50))

    @property
    def is_previewing(self) -> bool:
        return self._previewing

    def _generate_frame(self, color: tuple[int, int, int]) -> bytes:
        """Create a solid-colour JPEG image in memory."""
        img = Image.new("RGB", (self._width, self._height), color)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        return buffer.getvalue()


# ---------------------------------------------------------------------------
# Webcam implementation (OpenCV)
# ---------------------------------------------------------------------------

class WebcamCameraService:
    """USB/built-in webcam via OpenCV.

    The preview loop runs in a dedicated background thread, pushing JPEG
    frames into a bounded queue.  The main thread consumes frames from
    this queue via ``get_preview_frame()``.

    The queue has ``maxsize=2`` which acts as a natural backpressure valve:
    if the UI can't keep up, old frames are silently dropped.
    """

    name = "Webcam"

    def __init__(
        self,
        device_index: int = 0,
        preview_fps: int = 15,
        capture_quality: int = 95,
    ) -> None:
        self._device_index = device_index
        self._preview_fps = preview_fps
        self._capture_quality = capture_quality

        self._cap = None  # cv2.VideoCapture — lazy init
        self._previewing = False
        self._preview_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._frame_queue: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self._lock = threading.Lock()
        self._ready = False
        self._preview_filter: str = "classic"  # Active filter for preview frames

    @property
    def is_previewing(self) -> bool:
        return self._previewing

    @property
    def is_ready(self) -> bool:
        """Whether the camera device is open and ready."""
        return self._ready

    def warm_up(self) -> None:
        """Pre-open the camera in a background thread.

        Call this at app startup so the slow ``cv2.VideoCapture()`` init
        happens while the user is still on the idle screen.  By the time
        they tap START, the camera is already ready.
        """
        if self._ready or self._cap is not None:
            return
        threading.Thread(
            target=self._do_warm_up,
            name="webcam-warmup",
            daemon=True,
        ).start()

    def _do_warm_up(self) -> None:
        """Background thread: open the camera device."""
        try:
            self._ensure_capture()
            self._ready = True
            logger.info("Webcam warmed up and ready")
        except RuntimeError as e:
            logger.error("Webcam warm-up failed: %s", e)

    def _ensure_capture(self):
        """Open the camera device. May be slow — never call from the main thread."""
        if self._cap is None:
            import cv2
            self._cap = cv2.VideoCapture(self._device_index)
            if not self._cap.isOpened():
                raise RuntimeError(
                    f"Could not open camera device {self._device_index}. "
                    "Check that a webcam is connected and not in use by another app."
                )
            # Request the highest quality we can get — the camera will
            # negotiate down to its actual maximum resolution.
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            actual_w = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            logger.info(
                "Opened webcam device %d: %.0fx%.0f",
                self._device_index,
                actual_w,
                actual_h,
            )

    def start_preview(self) -> None:
        """Start the background preview capture loop.

        Returns immediately — camera init happens in the background thread
        so the UI is never blocked.
        """
        if self._previewing:
            return

        self._stop_event.clear()
        self._previewing = True

        self._preview_thread = threading.Thread(
            target=self._preview_loop,
            name="webcam-preview",
            daemon=True,
        )
        self._preview_thread.start()
        logger.info("Webcam preview starting (target %d fps)", self._preview_fps)

    def stop_preview(self) -> None:
        """Stop the background preview loop and wait for the thread."""
        if not self._previewing:
            return

        self._stop_event.set()
        self._previewing = False

        if self._preview_thread:
            self._preview_thread.join(timeout=2.0)
            self._preview_thread = None

        # Drain the queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Webcam preview stopped")

    def get_preview_frame(self) -> bytes | None:
        """Return the most recent preview frame, or None if unavailable."""
        frame = None
        # Drain the queue to get the latest frame (skip stale ones)
        while True:
            try:
                frame = self._frame_queue.get_nowait()
            except queue.Empty:
                break
        return frame

    def capture_photo(self) -> bytes:
        """Capture a full-resolution photo.

        If preview is running, we grab a frame directly from the capture
        device under lock for maximum quality.  If not, we briefly open
        the device, grab a frame, and return it.
        """
        import cv2

        with self._lock:
            self._ensure_capture()

            # Allow the camera a moment to auto-expose
            # Skip a few frames to get a properly exposed shot
            for _ in range(5):
                self._cap.read()

            ret, frame = self._cap.read()
            if not ret:
                raise RuntimeError("Failed to capture photo from webcam")

            # Mirror horizontally — matches the mirrored preview
            frame = cv2.flip(frame, 1)

            # Encode as JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._capture_quality]
            success, buffer = cv2.imencode(".jpg", frame, encode_params)
            if not success:
                raise RuntimeError("Failed to encode captured frame as JPEG")

            logger.info(
                "Photo captured: %dx%d (%d bytes)",
                frame.shape[1], frame.shape[0], len(buffer),
            )
            return bytes(buffer)

    def release(self) -> None:
        """Release the camera device. Call on app shutdown."""
        self.stop_preview()
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                logger.info("Webcam device released")

    @property
    def preview_filter(self) -> str:
        """The active filter applied to preview frames."""
        return self._preview_filter

    @preview_filter.setter
    def preview_filter(self, value: str) -> None:
        self._preview_filter = value

    @classmethod
    def _apply_filter_cv2(cls, frame, filter_name: str):
        """Apply a .cube LUT filter to a raw CV2 BGR frame.

        Uses Pillow's C-implemented Color3DLUT via the LUT registry
        for accurate, smooth color grading.
        """
        if filter_name in ("none", "classic", ""):
            return frame

        from photobooth.services.processing import get_lut_registry
        registry = get_lut_registry()
        if registry.has_lut(filter_name):
            return registry.apply_cv2(frame, filter_name)

        return frame  # Unknown filter — passthrough

    def _preview_loop(self) -> None:
        """Background thread: open camera then continuously capture frames."""
        import cv2

        # Open camera in this thread (may be slow — that's fine, we're off main thread)
        try:
            self._ensure_capture()
        except RuntimeError as e:
            logger.error("Failed to open camera: %s", e)
            self._previewing = False
            return

        interval = 1.0 / self._preview_fps

        while not self._stop_event.is_set():
            start = time.monotonic()

            with self._lock:
                if self._cap is None or not self._cap.isOpened():
                    break
                ret, frame = self._cap.read()

            if ret:
                # Mirror is handled by Kivy's flip_horizontal() in the UI layer

                # Preview at full resolution for crisp display.
                # On low-powered devices (RPi4), set PREVIEW_MAX_WIDTH env
                # var to downscale (e.g. 960).
                h, w = frame.shape[:2]
                max_preview_w = int(os.environ.get("PREVIEW_MAX_WIDTH", "0"))
                if max_preview_w > 0 and w > max_preview_w:
                    scale = max_preview_w / w
                    frame = cv2.resize(
                        frame, None, fx=scale, fy=scale,
                        interpolation=cv2.INTER_AREA,
                    )

                # Apply filter on the raw frame (fast — no JPEG decode/encode)
                active_filter = self._preview_filter
                if active_filter not in ("none", "classic", ""):
                    frame = self._apply_filter_cv2(frame, active_filter)

                # Encode frame as JPEG (single encode — no round-trip)
                success, buffer = cv2.imencode(
                    ".jpg", frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 85],
                )
                if success:
                    jpeg_bytes = bytes(buffer)
                    # Non-blocking put — drop frame if queue is full (backpressure)
                    try:
                        self._frame_queue.put_nowait(jpeg_bytes)
                    except queue.Full:
                        # Drop oldest frame and add new one
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            self._frame_queue.put_nowait(jpeg_bytes)
                        except queue.Full:
                            pass

            # Pace to target FPS
            elapsed = time.monotonic() - start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def list_webcams(max_check: int = 5) -> list[dict]:
    """Probe for available webcam devices.

    Returns a list of dicts with ``index`` and ``name`` keys.
    """
    devices = []
    try:
        import cv2
    except ImportError:
        return devices

    for i in range(max_check):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            devices.append({
                "index": i,
                "name": f"Camera {i} ({w}x{h})",
            })
            cap.release()
    return devices


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_camera_service(backend: str, **kwargs) -> CameraService:
    """Factory function — returns the right camera service for the config.

    Args:
        backend: One of ``"stub"``, ``"webcam"``, ``"gphoto2"``.

    Returns:
        A ``CameraService``-compatible instance.

    Raises:
        ValueError: If the backend name is unknown.
    """
    if backend == "stub":
        return StubCameraService(**kwargs)
    if backend == "webcam":
        return WebcamCameraService(**kwargs)
    if backend == "gphoto2":
        from photobooth.services.gphoto2_camera import GPhoto2CameraService
        return GPhoto2CameraService(**kwargs)
    raise ValueError(f"Unknown camera backend: {backend!r}")
