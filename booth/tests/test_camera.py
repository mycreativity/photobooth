"""Unit tests for the camera service."""

import queue
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from photobooth.services.camera import (
    CameraService,
    StubCameraService,
    WebcamCameraService,
    create_camera_service,
    list_webcams,
)


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
