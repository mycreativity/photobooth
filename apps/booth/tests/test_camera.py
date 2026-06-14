"""Unit tests for the camera service."""

import queue
import threading
import time

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from photobooth.services.camera import (
    CameraService,
    StubCameraService,
    WebcamCameraService,
    create_camera_service,
    list_webcams,
)


PREVIEW_THREAD_NAME = "webcam-preview"


def _live_preview_threads() -> list[threading.Thread]:
    """All currently-alive preview loop threads (across every instance)."""
    return [
        t for t in threading.enumerate()
        if t.name == PREVIEW_THREAD_NAME and t.is_alive()
    ]


def _make_webcam_with_fake_capture() -> WebcamCameraService:
    """A webcam service whose camera open is faked (no hardware needed).

    The preview loop runs for real (real cv2.imencode on a tiny frame),
    so the threading lifecycle is exercised exactly as in production.
    """
    import numpy as np

    svc = WebcamCameraService(preview_fps=60)
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, np.zeros((48, 64, 3), dtype=np.uint8))

    def _fake_ensure():
        svc._cap = mock_cap

    svc._ensure_capture = _fake_ensure  # type: ignore[assignment]
    return svc


def _wait_until(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


class TestStubCameraService:
    """Tests for the stub camera backend."""

    def test_implements_protocol(self):
        assert isinstance(StubCameraService(), CameraService)

    def test_has_name(self):
        assert StubCameraService.name == "Stub Camera"

    def test_not_previewing_by_default(self):
        svc = StubCameraService()
        assert not svc.is_previewing

    def test_start_stop_preview(self):
        svc = StubCameraService()
        svc.start_preview()
        assert svc.is_previewing
        svc.stop_preview()
        assert not svc.is_previewing

    def test_get_preview_frame_returns_none_when_not_previewing(self):
        svc = StubCameraService()
        assert svc.get_preview_frame() is None

    def test_get_preview_frame_returns_jpeg_bytes(self):
        svc = StubCameraService()
        svc.start_preview()
        frame = svc.get_preview_frame()
        assert isinstance(frame, bytes)
        assert frame[:2] == b"\xff\xd8"  # JPEG magic bytes

    def test_capture_photo_returns_jpeg_bytes(self):
        svc = StubCameraService()
        photo = svc.capture_photo()
        assert isinstance(photo, bytes)
        assert photo[:2] == b"\xff\xd8"

    def test_custom_frame_dimensions(self):
        svc = StubCameraService(frame_width=320, frame_height=240)
        frame = svc.capture_photo()
        assert len(frame) > 0


class TestWebcamCameraService:
    """Tests for the webcam backend (mocked cv2)."""

    def test_has_name(self):
        assert WebcamCameraService.name == "Webcam"

    def test_not_previewing_by_default(self):
        svc = WebcamCameraService()
        assert not svc.is_previewing

    @patch("photobooth.services.camera.cv2", create=True)
    def test_capture_returns_jpeg(self, mock_cv2):
        """Test capture with mocked OpenCV."""
        import numpy as np

        # Mock VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.get.return_value = 640.0
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CAP_PROP_FRAME_WIDTH = 3
        mock_cv2.CAP_PROP_FRAME_HEIGHT = 4
        mock_cv2.IMWRITE_JPEG_QUALITY = 1

        # Mock imencode to return valid JPEG bytes
        mock_cv2.imencode.return_value = (True, np.array([0xFF, 0xD8, 0x00], dtype=np.uint8))

        svc = WebcamCameraService(device_index=0)
        photo = svc.capture_photo()
        assert isinstance(photo, bytes)
        svc.release()

    def test_release_without_open(self):
        """Release should work even if camera was never opened."""
        svc = WebcamCameraService()
        svc.release()  # Should not raise


class TestWebcamPreviewThreadLifecycle:
    """Regression cover for the preview-thread leak.

    Bug: every preview thread shared one ``_stop_event``. A fast
    stop→start (e.g. navigating back to idle and starting again) could
    revive the old thread instead of killing it, leaking busy-looping
    threads that pegged the CPU and fought over the camera, making the
    live preview go black.
    """

    def test_start_creates_exactly_one_thread(self):
        svc = _make_webcam_with_fake_capture()
        try:
            svc.start_preview()
            assert _wait_until(lambda: len(_live_preview_threads()) == 1)
            assert svc.is_previewing
        finally:
            svc.stop_preview()

    def test_stop_terminates_the_thread(self):
        svc = _make_webcam_with_fake_capture()
        svc.start_preview()
        thread = svc._preview_thread
        assert _wait_until(lambda: thread.is_alive())
        svc.stop_preview()
        assert not svc.is_previewing
        assert not thread.is_alive()
        assert _live_preview_threads() == []

    def test_double_start_is_idempotent(self):
        """Starting twice must not spawn a second preview thread."""
        svc = _make_webcam_with_fake_capture()
        try:
            svc.start_preview()
            assert _wait_until(lambda: len(_live_preview_threads()) == 1)
            svc.start_preview()  # no-op
            time.sleep(0.2)
            assert len(_live_preview_threads()) == 1
        finally:
            svc.stop_preview()

    def test_old_thread_is_not_revived_by_restart(self):
        """The core race: after stop+start the OLD thread must stay dead."""
        svc = _make_webcam_with_fake_capture()
        try:
            svc.start_preview()
            first = svc._preview_thread
            assert _wait_until(lambda: first.is_alive())

            svc.stop_preview()
            assert not first.is_alive()

            svc.start_preview()
            second = svc._preview_thread
            assert second is not first
            assert _wait_until(lambda: second.is_alive())
            # Only the new thread is alive — the old one was not revived.
            assert _live_preview_threads() == [second]
        finally:
            svc.stop_preview()

    def test_repeated_cycles_do_not_leak_threads(self):
        """Many stop/start cycles must never accumulate live threads."""
        svc = _make_webcam_with_fake_capture()
        try:
            for _ in range(8):
                svc.start_preview()
                assert _wait_until(lambda: len(_live_preview_threads()) == 1)
                svc.stop_preview()
                assert _wait_until(lambda: len(_live_preview_threads()) == 0)
            # Final state: nothing left running.
            assert _live_preview_threads() == []
        finally:
            svc.stop_preview()

    def test_release_stops_preview_thread(self):
        svc = _make_webcam_with_fake_capture()
        svc.start_preview()
        assert _wait_until(lambda: len(_live_preview_threads()) == 1)
        svc.release()
        assert _wait_until(lambda: len(_live_preview_threads()) == 0)
        assert not svc.is_ready  # release resets readiness so warm_up re-opens


class TestCameraFactory:
    """Tests for the camera factory function."""

    def test_creates_stub_backend(self):
        svc = create_camera_service("stub")
        assert isinstance(svc, StubCameraService)

    def test_creates_webcam_backend(self):
        svc = create_camera_service("webcam")
        assert isinstance(svc, WebcamCameraService)

    def test_stub_with_custom_kwargs(self):
        svc = create_camera_service("stub", frame_width=320, frame_height=240)
        assert isinstance(svc, StubCameraService)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown camera backend"):
            create_camera_service("nonexistent")
