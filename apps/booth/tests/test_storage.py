"""Unit tests for the storage service."""

import pytest
from pathlib import Path

from photobooth.services.storage import StorageService


@pytest.fixture
def storage(tmp_path):
    """Create a StorageService in a temp directory."""
    return StorageService(
        photo_dir=str(tmp_path / "photos"),
        database=str(tmp_path / "test.db"),
    )


@pytest.fixture
def sample_jpeg():
    """Minimal valid JPEG bytes."""
    from PIL import Image
    from io import BytesIO
    img = Image.new("RGB", (100, 80), (255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestStorageInit:
    def test_creates_database(self, storage, tmp_path):
        assert (tmp_path / "test.db").exists()

    def test_creates_photo_dir(self, storage, tmp_path):
        assert (tmp_path / "photos").is_dir()

    def test_initial_counts_are_zero(self, storage):
        assert storage.get_session_count() == 0
        assert storage.get_photo_count() == 0


class TestSessions:
    def test_create_session(self, storage):
        sid = storage.create_session(theme="classic", language="nl", camera="webcam")
        assert sid == 1

    def test_create_multiple_sessions(self, storage):
        s1 = storage.create_session()
        s2 = storage.create_session()
        assert s2 == s1 + 1

    def test_get_session(self, storage):
        sid = storage.create_session(theme="classic", language="en", camera="stub")
        session = storage.get_session(sid)
        assert session is not None
        assert session["theme"] == "classic"
        assert session["language"] == "en"
        assert session["camera"] == "stub"

    def test_get_nonexistent_session(self, storage):
        assert storage.get_session(999) is None

    def test_session_count_increments(self, storage):
        storage.create_session()
        storage.create_session()
        assert storage.get_session_count() == 2


class TestPhotoStorage:
    def test_save_photo(self, storage, sample_jpeg):
        sid = storage.create_session()
        rel_path = storage.save_photo(sid, seq=1, jpeg_data=sample_jpeg)
        assert "original_1.jpg" in rel_path

    def test_photo_file_exists_on_disk(self, storage, sample_jpeg):
        sid = storage.create_session()
        rel_path = storage.save_photo(sid, seq=1, jpeg_data=sample_jpeg)
        abs_path = storage.get_photo_path(rel_path)
        assert abs_path.exists()
        assert abs_path.read_bytes() == sample_jpeg

    def test_photo_dimensions_recorded(self, storage, sample_jpeg):
        sid = storage.create_session()
        storage.save_photo(sid, seq=1, jpeg_data=sample_jpeg)
        photos = storage.get_session_photos(sid)
        assert len(photos) == 1
        assert photos[0]["width"] == 100
        assert photos[0]["height"] == 80

    def test_multiple_photos_per_session(self, storage, sample_jpeg):
        sid = storage.create_session()
        storage.save_photo(sid, seq=1, jpeg_data=sample_jpeg)
        storage.save_photo(sid, seq=2, jpeg_data=sample_jpeg)
        storage.save_photo(sid, seq=3, jpeg_data=sample_jpeg)
        photos = storage.get_session_photos(sid)
        assert len(photos) == 3
        assert [p["seq"] for p in photos] == [1, 2, 3]

    def test_photo_count_increments(self, storage, sample_jpeg):
        sid = storage.create_session()
        storage.save_photo(sid, seq=1, jpeg_data=sample_jpeg)
        storage.save_photo(sid, seq=2, jpeg_data=sample_jpeg)
        assert storage.get_photo_count() == 2

    def test_session_photo_count_updated(self, storage, sample_jpeg):
        sid = storage.create_session()
        storage.save_photo(sid, seq=1, jpeg_data=sample_jpeg)
        session = storage.get_session(sid)
        assert session["photo_count"] == 1

    def test_size_bytes_recorded(self, storage, sample_jpeg):
        sid = storage.create_session()
        storage.save_photo(sid, seq=1, jpeg_data=sample_jpeg)
        photos = storage.get_session_photos(sid)
        assert photos[0]["size_bytes"] == len(sample_jpeg)


class TestStorageClose:
    def test_close_and_reopen(self, tmp_path, sample_jpeg):
        db_path = str(tmp_path / "test.db")
        photo_dir = str(tmp_path / "photos")

        s1 = StorageService(photo_dir=photo_dir, database=db_path)
        sid = s1.create_session()
        s1.save_photo(sid, seq=1, jpeg_data=sample_jpeg)
        s1.close()

        # Reopen — data should persist
        s2 = StorageService(photo_dir=photo_dir, database=db_path)
        assert s2.get_session_count() == 1
        assert s2.get_photo_count() == 1
        s2.close()
