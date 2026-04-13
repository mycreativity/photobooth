"""Application configuration management.

Reads booth settings from a TOML file and exposes them as typed dataclasses.
Uses Python 3.11+ stdlib `tomllib` — no external dependencies needed.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self


@dataclass(frozen=True)
class AppConfig:
    """Top-level application settings."""

    name: str = "Photobooth"
    event_name: str = ""              # e.g. "Wedding Jan & Lisa" — groups all sessions
    fullscreen: bool = False
    width: int = 1280
    height: int = 800
    fps: int = 30
    language: str = "nl"
    theme: str = "classic"
    background_video: str = ""


@dataclass(frozen=True)
class CameraConfig:
    """Camera backend and capture settings."""

    backend: str = "webcam"
    device_index: int = 0
    preview_fps: int = 15
    capture_format: str = "jpeg"
    capture_quality: int = 95
    # DSLR-specific (gphoto2 backend)
    iso: str = "auto"               # "auto", "100", "200", "400", etc.
    aperture: str = ""               # "5.6", "8", etc. (empty = don't set)
    shutter_speed: str = "auto"      # "auto", "1/60", "1/125", etc.


@dataclass(frozen=True)
class CountdownConfig:
    """Countdown timer settings."""

    first_countdown: int = 5       # Seconds before the first photo
    between_shots: int = 3         # "Panic gap" seconds between subsequent photos
    photos_per_session: int = 1
    sound_enabled: bool = True


@dataclass(frozen=True)
class ProcessingConfig:
    """Image processing pipeline settings."""

    max_workers: int = 2
    output_dir: str = "photos"
    thumbnail_size: tuple[int, int] = (320, 240)


@dataclass(frozen=True)
class PrintingConfig:
    """Printer settings."""

    enabled: bool = False
    printer_name: str = ""
    copies: int = 1


@dataclass(frozen=True)
class PrintLayoutConfig:
    """Print layout dimensions and styling.

    Controls how photos are composited onto a printable image.
    Default values target a standard 10×15 cm print at 300 DPI.
    """

    width: int = 1200              # px (10 cm @ 300 DPI)
    height: int = 1800             # px (15 cm @ 300 DPI)
    photo_ratio: float = 1.4       # 7:5 landscape
    branding_height: int = 270     # px for logo/text bar at bottom
    padding: int = 30              # px between photos and edges
    background_color: str = "#FFFFFF"
    logo_path: str = "assets/images/logo.png"


@dataclass(frozen=True)
class GlamourConfig:
    """Glamour after-effect parameters.

    All values are 0.0–1.0 intensity floats.
    0.0 = effect disabled, 1.0 = maximum intensity.
    """

    skin_smooth: float = 0.7    # Bilateral filter blend ratio
    warmth: float = 0.5         # Color warmth/glow
    vignette: float = 0.5       # Vignette darkening
    eye_enhance: float = 0.5    # Eye contrast/sharpness
    makeup: float = 0.5         # Lip tint + cheek blush
    sparkles: float = 0.3       # Light sparkle overlay
    soft_glow: float = 0.4      # Orton soft glow / bloom


@dataclass(frozen=True)
class StorageConfig:
    """Storage and database settings."""

    database: str = "photobooth.db"
    photo_dir: str = "photos"


@dataclass(frozen=True)
class LedConfig:
    """LED strip settings (SK6812 RGBW on GPIO)."""

    enabled: bool = True
    led_count: int = 80
    gpio_pin: int = 18
    brightness: int = 80          # 0-255 default brightness
    flash_brightness: int = 255   # Max brightness for photo flash


@dataclass(frozen=True)
class EmailConfig:
    """SMTP email delivery settings."""

    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""       # App-specific password
    from_address: str = ""
    subject: str = "Your Photobooth Photos!"


@dataclass(frozen=True)
class ServerConfig:
    """Admin server connection settings."""

    enabled: bool = False
    url: str = "ws://localhost:8000"
    booth_id: str = "booth-001"
    booth_name: str = "Photobooth 1"
    api_key: str = ""
    heartbeat_interval: int = 10
    reconnect_delay: int = 5
    reconnect_max_delay: int = 60


@dataclass(frozen=True)
class BoothConfig:
    """Root configuration object aggregating all sub-configs."""

    app: AppConfig = field(default_factory=AppConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    countdown: CountdownConfig = field(default_factory=CountdownConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    printing: PrintingConfig = field(default_factory=PrintingConfig)
    print_layout: PrintLayoutConfig = field(default_factory=PrintLayoutConfig)
    glamour: GlamourConfig = field(default_factory=GlamourConfig)
    led: LedConfig = field(default_factory=LedConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Build a BoothConfig from a raw dictionary (e.g. parsed TOML)."""
        return cls(
            app=AppConfig(**data.get("app", {})),
            camera=CameraConfig(**data.get("camera", {})),
            countdown=CountdownConfig(**data.get("countdown", {})),
            processing=_build_processing_config(data.get("processing", {})),
            printing=PrintingConfig(**data.get("printing", {})),
            print_layout=PrintLayoutConfig(**data.get("print_layout", {})),
            glamour=GlamourConfig(**data.get("glamour", {})),
            led=LedConfig(**data.get("led", {})),
            storage=StorageConfig(**data.get("storage", {})),
            email=EmailConfig(**data.get("email", {})),
            server=ServerConfig(**data.get("server", {})),
        )


def _build_processing_config(raw: dict) -> ProcessingConfig:
    """Handle special conversions for ProcessingConfig (e.g. list → tuple)."""
    if "thumbnail_size" in raw and isinstance(raw["thumbnail_size"], list):
        raw = {**raw, "thumbnail_size": tuple(raw["thumbnail_size"])}
    return ProcessingConfig(**raw)


def load_config(path: Path | None = None) -> BoothConfig:
    """Load configuration from a TOML file, falling back to defaults.

    Args:
        path: Path to the TOML config file. If None or the file doesn't exist,
              returns a BoothConfig with all default values.

    Returns:
        A fully populated BoothConfig instance.
    """
    if path is None or not path.exists():
        return BoothConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    return BoothConfig.from_dict(data)


# Mapping from dotted setting keys → (sub-config attr, field name, type cast)
_SETTING_MAP: dict[str, tuple[str, str, type]] = {
    "app.event_name": ("app", "event_name", str),
    "app.language": ("app", "language", str),
    "app.theme": ("app", "theme", str),
    "camera.backend": ("camera", "backend", str),
    "camera.iso": ("camera", "iso", str),
    "camera.aperture": ("camera", "aperture", str),
    "camera.shutter_speed": ("camera", "shutter_speed", str),
    "camera.preview_fps": ("camera", "preview_fps", int),
    "countdown.first_countdown": ("countdown", "first_countdown", int),
    "countdown.between_shots": ("countdown", "between_shots", int),
    "glamour.skin_smooth": ("glamour", "skin_smooth", float),
    "glamour.warmth": ("glamour", "warmth", float),
    "glamour.vignette": ("glamour", "vignette", float),
    "glamour.eye_enhance": ("glamour", "eye_enhance", float),
    "glamour.makeup": ("glamour", "makeup", float),
    "glamour.sparkles": ("glamour", "sparkles", float),
    "glamour.soft_glow": ("glamour", "soft_glow", float),
}


def apply_overrides(config: BoothConfig, overrides: dict[str, str]) -> BoothConfig:
    """Return a new BoothConfig with SQLite setting overrides applied.

    Keys in *overrides* use dotted notation matching TOML structure,
    e.g. ``"app.event_name"`` or ``"countdown.first_countdown"``.
    Unknown keys are silently ignored.
    """
    import dataclasses

    # Group overrides by sub-config section
    section_updates: dict[str, dict[str, object]] = {}
    for key, raw_value in overrides.items():
        if key not in _SETTING_MAP:
            continue
        section, field, cast = _SETTING_MAP[key]
        section_updates.setdefault(section, {})[field] = cast(raw_value)

    if not section_updates:
        return config

    replacements: dict[str, object] = {}
    for section, fields in section_updates.items():
        sub_config = getattr(config, section)
        replacements[section] = dataclasses.replace(sub_config, **fields)

    return dataclasses.replace(config, **replacements)

