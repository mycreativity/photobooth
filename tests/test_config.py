"""Unit tests for the configuration module."""

from pathlib import Path

import pytest

from photobooth.config import (
    AppConfig,
    BoothConfig,
    CameraConfig,
    CountdownConfig,
    PrintingConfig,
    ProcessingConfig,
    StorageConfig,
    load_config,
)


class TestDefaultConfig:
    """Ensure sensible defaults when no config file exists."""

    def test_load_config_returns_defaults_when_path_is_none(self):
        config = load_config(None)
        assert isinstance(config, BoothConfig)
        assert config.app.name == "Photobooth"

    def test_load_config_returns_defaults_when_file_missing(self):
        config = load_config(Path("/nonexistent/booth.toml"))
        assert config.camera.backend == "webcam"

    def test_default_app_config(self):
        cfg = AppConfig()
        assert cfg.fullscreen is False
        assert cfg.width == 1280
        assert cfg.height == 800
        assert cfg.fps == 30
        assert cfg.language == "nl"
        assert cfg.theme == "classic"

    def test_default_camera_config(self):
        cfg = CameraConfig()
        assert cfg.backend == "webcam"
        assert cfg.preview_fps == 15

    def test_default_countdown_config(self):
        cfg = CountdownConfig()
        assert cfg.first_countdown == 5
        assert cfg.between_shots == 3
        assert cfg.sound_enabled is True

    def test_default_processing_config(self):
        cfg = ProcessingConfig()
        assert cfg.thumbnail_size == (320, 240)
        assert cfg.max_workers == 2

    def test_default_printing_config(self):
        cfg = PrintingConfig()
        assert cfg.enabled is False

    def test_default_storage_config(self):
        cfg = StorageConfig()
        assert cfg.database == "photobooth.db"


class TestConfigFromFile:
    """Test loading config from a real TOML file."""

    def test_load_partial_config_merges_with_defaults(self, tmp_path):
        toml_content = b"""
[app]
name = "My Booth"
fullscreen = true
language = "en"
theme = "classic"

[camera]
backend = "gphoto2"
"""
        config_file = tmp_path / "test.toml"
        config_file.write_bytes(toml_content)

        config = load_config(config_file)

        # Overridden values
        assert config.app.name == "My Booth"
        assert config.app.fullscreen is True
        assert config.app.language == "en"
        assert config.camera.backend == "gphoto2"

        # Defaults preserved for sections not in the file
        assert config.printing.enabled is False
        assert config.countdown.first_countdown == 5

    def test_thumbnail_size_list_converted_to_tuple(self, tmp_path):
        toml_content = b"""
[processing]
thumbnail_size = [640, 480]
"""
        config_file = tmp_path / "test.toml"
        config_file.write_bytes(toml_content)

        config = load_config(config_file)
        assert config.processing.thumbnail_size == (640, 480)
        assert isinstance(config.processing.thumbnail_size, tuple)


class TestBoothConfigFromDict:
    """Test the from_dict class method directly."""

    def test_empty_dict_gives_all_defaults(self):
        config = BoothConfig.from_dict({})
        assert config == BoothConfig()

    def test_full_override(self):
        data = {
            "app": {
                "name": "Test",
                "fullscreen": True,
                "width": 800,
                "height": 480,
                "fps": 60,
                "language": "en",
                "theme": "classic",
            },
            "camera": {
                "backend": "gphoto2",
                "preview_fps": 20,
                "capture_format": "raw",
                "capture_quality": 100,
            },
            "countdown": {"first_countdown": 10, "between_shots": 5, "sound_enabled": False},
            "processing": {
                "max_workers": 4,
                "output_dir": "/tmp/photos",
                "thumbnail_size": [800, 600],
            },
            "printing": {"enabled": True, "printer_name": "Canon", "copies": 2},
            "storage": {"database": "test.db", "photo_dir": "/tmp/pics"},
        }
        config = BoothConfig.from_dict(data)

        assert config.app.name == "Test"
        assert config.app.fps == 60
        assert config.app.language == "en"
        assert config.camera.backend == "gphoto2"
        assert config.countdown.first_countdown == 10
        assert config.countdown.between_shots == 5
        assert config.processing.max_workers == 4
        assert config.processing.thumbnail_size == (800, 600)
        assert config.printing.enabled is True
        assert config.printing.printer_name == "Canon"
        assert config.storage.database == "test.db"

    def test_config_is_immutable(self):
        config = BoothConfig()
        with pytest.raises(AttributeError):
            config.app = AppConfig(name="Hacked")  # type: ignore[misc]
