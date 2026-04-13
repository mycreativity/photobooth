"""Print layout compositing engine.

Generates print-ready images at 300 DPI on a standard 10×15 cm photo
in portrait orientation.  Each layout arranges captured photos on a
white canvas with a themed branding bar at the bottom.

Print dimensions::

    10 cm × 15 cm  →  1200 × 1800 px @ 300 DPI

Layout arrangements::

    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │              │  │              │  │ ┌────┐┌────┐ │
    │   ┌──────┐   │  │  ┌────────┐  │  │ │    ││    │ │
    │   │      │   │  │  │ LARGE  │  │  │ │ 1  ││ 2  │ │
    │   │SINGLE│   │  │  │   1    │  │  │ │    ││    │ │
    │   │      │   │  │  └────────┘  │  │ └────┘└────┘ │
    │   └──────┘   │  │  ┌───┐┌───┐  │  │ ┌────┐┌────┐ │
    │              │  │  │ 2 ││ 3 │  │  │ │    ││    │ │
    │ ╔══════════╗ │  │  └───┘└───┘  │  │ │ 3  ││ 4  │ │
    │ ║ BRANDING ║ │  │ ╔══════════╗ │  │ │    ││    │ │
    │ ╚══════════╝ │  │ ║ BRANDING ║ │  │ └────┘└────┘ │
    └──────────────┘  │ ╚══════════╝ │  │ ╔══════════╗ │
                      └──────────────┘  │ ║ BRANDING ║ │
                                        │ ╚══════════╝ │
                                        └──────────────┘

Photo aspect ratio: **7:5 landscape** (1.4:1) — mathematically optimised
to maximise print area utilisation across all three layouts.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Print constants
# ---------------------------------------------------------------------------

PRINT_WIDTH = 1200       # px (10 cm @ 300 DPI)
PRINT_HEIGHT = 1800      # px (15 cm @ 300 DPI)
PHOTO_RATIO = 7 / 5      # 1.4 — landscape aspect ratio for photos
BRANDING_HEIGHT = 270     # px (~15% of total height)
PADDING = 30              # px between photos and edges
OUTPUT_QUALITY = 95       # JPEG output quality

# Derived
_PHOTO_AREA_TOP = PADDING
_PHOTO_AREA_BOTTOM = PRINT_HEIGHT - BRANDING_HEIGHT - PADDING
_PHOTO_AREA_HEIGHT = _PHOTO_AREA_BOTTOM - _PHOTO_AREA_TOP
_PHOTO_AREA_LEFT = PADDING
_PHOTO_AREA_RIGHT = PRINT_WIDTH - PADDING
_PHOTO_AREA_WIDTH = _PHOTO_AREA_RIGHT - _PHOTO_AREA_LEFT


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def crop_to_ratio(jpeg_data: bytes, ratio: float = PHOTO_RATIO) -> bytes:
    """Center-crop a JPEG image to the target aspect ratio.

    Args:
        jpeg_data: Raw JPEG bytes.
        ratio: Target width/height ratio (default 7:5 = 1.4).

    Returns:
        Cropped JPEG bytes.
    """
    img = Image.open(io.BytesIO(jpeg_data))
    w, h = img.size
    current_ratio = w / h

    if abs(current_ratio - ratio) < 0.01:
        return jpeg_data  # Already correct ratio

    if current_ratio > ratio:
        # Too wide — crop horizontally
        new_w = int(h * ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        # Too tall — crop vertically
        new_h = int(w / ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=OUTPUT_QUALITY)
    return buf.getvalue()


def compose_print(
    layout: str,
    photos: list[bytes],
    event_name: str = "",
    logo_path: str | None = None,
    theme_colors: dict | None = None,
    font_path: str | None = None,
) -> bytes:
    """Compose a print-ready image for the given layout.

    Args:
        layout: One of 'single', 'strip', 'grid'.
        photos: List of JPEG bytes (already cropped to 7:5).
        event_name: Event name for the branding bar.
        logo_path: Absolute path to the logo image file.
        theme_colors: Dict with 'primary', 'background', 'text' as hex strings.
        font_path: Path to TTF font file for branding text.

    Returns:
        Composed print image as JPEG bytes (1200×1800 px).
    """
    compositors = {
        "single": _compose_single,
        "strip": _compose_strip,
        "grid": _compose_grid,
    }
    compositor = compositors.get(layout, _compose_single)
    img = compositor(photos)
    _draw_branding_bar(img, event_name, logo_path, theme_colors, font_path)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=OUTPUT_QUALITY)
    result = buf.getvalue()

    logger.info(
        "[Print composite] layout=%s, %d photos, %d bytes",
        layout, len(photos), len(result),
    )
    return result


# ---------------------------------------------------------------------------
# Layout compositors
# ---------------------------------------------------------------------------

def _compose_single(photos: list[bytes]) -> Image.Image:
    """Single photo layout — one large photo centered.

    ┌──────────────┐
    │   ┌──────┐   │
    │   │      │   │
    │   │PHOTO │   │
    │   │      │   │
    │   └──────┘   │
    │ ╔══════════╗ │
    │ ║ BRANDING ║ │
    │ ╚══════════╝ │
    └──────────────┘
    """
    canvas = Image.new("RGB", (PRINT_WIDTH, PRINT_HEIGHT), "white")

    if not photos:
        return canvas

    photo = _load_and_fit(
        photos[0],
        _PHOTO_AREA_WIDTH,
        _PHOTO_AREA_HEIGHT,
    )
    # Center the photo in the available area
    x = _PHOTO_AREA_LEFT + (_PHOTO_AREA_WIDTH - photo.width) // 2
    y = _PHOTO_AREA_TOP + (_PHOTO_AREA_HEIGHT - photo.height) // 2
    canvas.paste(photo, (x, y))

    return canvas


def _compose_strip(photos: list[bytes]) -> Image.Image:
    """Strip layout — 1 large hero + 2 smaller photos below.

    ┌──────────────┐
    │  ┌────────┐  │
    │  │ LARGE  │  │
    │  │   1    │  │
    │  └────────┘  │
    │  ┌───┐┌───┐  │
    │  │ 2 ││ 3 │  │
    │  └───┘└───┘  │
    │ ╔══════════╗ │
    │ ║ BRANDING ║ │
    │ ╚══════════╝ │
    └──────────────┘
    """
    canvas = Image.new("RGB", (PRINT_WIDTH, PRINT_HEIGHT), "white")

    if not photos:
        return canvas

    # Calculate sizes
    # Hero photo: full width, proportional height
    hero_w = _PHOTO_AREA_WIDTH
    hero_h = int(hero_w / PHOTO_RATIO)

    # Small photos: half width minus gap
    small_w = (_PHOTO_AREA_WIDTH - PADDING) // 2
    small_h = int(small_w / PHOTO_RATIO)

    # Total height needed
    total_h = hero_h + PADDING + small_h

    # If it doesn't fit, scale down proportionally
    if total_h > _PHOTO_AREA_HEIGHT:
        scale = _PHOTO_AREA_HEIGHT / total_h
        hero_w = int(hero_w * scale)
        hero_h = int(hero_h * scale)
        small_w = int(small_w * scale)
        small_h = int(small_h * scale)
        total_h = hero_h + PADDING + small_h

    # Vertical centering
    start_y = _PHOTO_AREA_TOP + (_PHOTO_AREA_HEIGHT - total_h) // 2

    # Place hero photo (centered)
    hero = _load_and_fit(photos[0], hero_w, hero_h)
    hero_x = _PHOTO_AREA_LEFT + (_PHOTO_AREA_WIDTH - hero.width) // 2
    canvas.paste(hero, (hero_x, start_y))

    # Place small photos
    small_y = start_y + hero_h + PADDING

    if len(photos) > 1:
        small1 = _load_and_fit(photos[1], small_w, small_h)
        small1_x = _PHOTO_AREA_LEFT + (_PHOTO_AREA_WIDTH - 2 * small_w - PADDING) // 2
        canvas.paste(small1, (small1_x, small_y))

    if len(photos) > 2:
        small2 = _load_and_fit(photos[2], small_w, small_h)
        small2_x = small1_x + small_w + PADDING
        canvas.paste(small2, (small2_x, small_y))

    return canvas


def _compose_grid(photos: list[bytes]) -> Image.Image:
    """Grid layout — 2×2 grid of equal photos.

    ┌──────────────┐
    │ ┌────┐┌────┐ │
    │ │ 1  ││ 2  │ │
    │ └────┘└────┘ │
    │ ┌────┐┌────┐ │
    │ │ 3  ││ 4  │ │
    │ └────┘└────┘ │
    │ ╔══════════╗ │
    │ ║ BRANDING ║ │
    │ ╚══════════╝ │
    └──────────────┘
    """
    canvas = Image.new("RGB", (PRINT_WIDTH, PRINT_HEIGHT), "white")

    if not photos:
        return canvas

    # Each cell: half width, half height (minus gaps)
    cell_w = (_PHOTO_AREA_WIDTH - PADDING) // 2
    cell_h = int(cell_w / PHOTO_RATIO)

    # Total height for 2 rows
    total_h = cell_h * 2 + PADDING

    # Scale down if needed
    if total_h > _PHOTO_AREA_HEIGHT:
        scale = _PHOTO_AREA_HEIGHT / total_h
        cell_w = int(cell_w * scale)
        cell_h = int(cell_h * scale)
        total_h = cell_h * 2 + PADDING

    # Center the grid vertically
    start_y = _PHOTO_AREA_TOP + (_PHOTO_AREA_HEIGHT - total_h) // 2
    start_x = _PHOTO_AREA_LEFT + (_PHOTO_AREA_WIDTH - cell_w * 2 - PADDING) // 2

    positions = [
        (start_x, start_y),                              # Top-left
        (start_x + cell_w + PADDING, start_y),            # Top-right
        (start_x, start_y + cell_h + PADDING),            # Bottom-left
        (start_x + cell_w + PADDING, start_y + cell_h + PADDING),  # Bottom-right
    ]

    for i, (px, py) in enumerate(positions):
        if i < len(photos) and photos[i]:
            cell = _load_and_fit(photos[i], cell_w, cell_h)
            canvas.paste(cell, (px, py))

    return canvas


# ---------------------------------------------------------------------------
# Branding bar
# ---------------------------------------------------------------------------

def _draw_branding_bar(
    canvas: Image.Image,
    event_name: str,
    logo_path: str | None,
    theme_colors: dict | None = None,
    font_path: str | None = None,
) -> None:
    """Draw the branding bar at the bottom of the print.

    Layout: [Logo (left)] [Event name (center)] [Date (right)]

    Colors and font match the active theme.
    """
    colors = theme_colors or {}
    bar_bg = colors.get("bar_background", "#1C2028")
    bar_text = colors.get("bar_text", "#EDE8D0")
    bar_accent = colors.get("bar_accent", "#C29958")

    bar_y = PRINT_HEIGHT - BRANDING_HEIGHT
    draw = ImageDraw.Draw(canvas)

    # Draw bar background
    draw.rectangle(
        [0, bar_y, PRINT_WIDTH, PRINT_HEIGHT],
        fill=bar_bg,
    )

    # Load fonts
    title_font = _load_font(font_path, size=36)
    date_font = _load_font(font_path, size=22)

    # Accent line at top of bar
    line_y = bar_y + 8
    draw.rectangle(
        [PADDING, line_y, PRINT_WIDTH - PADDING, line_y + 3],
        fill=bar_accent,
    )

    content_y_center = bar_y + BRANDING_HEIGHT // 2

    # Logo (left side)
    logo_right_edge = PADDING
    if logo_path:
        try:
            logo_path_obj = Path(logo_path)
            if not logo_path_obj.is_absolute():
                logo_path_obj = Path.cwd() / logo_path_obj
            if logo_path_obj.exists():
                logo = Image.open(logo_path_obj).convert("RGBA")
                # Scale logo to fit branding bar height (with padding)
                max_logo_h = BRANDING_HEIGHT - 60
                max_logo_w = 300
                logo.thumbnail((max_logo_w, max_logo_h), Image.LANCZOS)
                logo_x = PADDING + 10
                logo_y = content_y_center - logo.height // 2
                canvas.paste(logo, (logo_x, logo_y), logo)
                logo_right_edge = logo_x + logo.width + 20
        except Exception as e:
            logger.warning("Failed to load logo: %s", e)

    # Event name (center)
    if event_name:
        # Calculate text position — centered between logo and date area
        text_area_left = max(logo_right_edge, PRINT_WIDTH // 4)
        text_area_right = PRINT_WIDTH - PADDING - 200  # Reserve space for date
        text_center_x = (text_area_left + text_area_right) // 2
        text_y = content_y_center - 20

        bbox = draw.textbbox((0, 0), event_name, font=title_font)
        text_w = bbox[2] - bbox[0]
        draw.text(
            (text_center_x - text_w // 2, text_y),
            event_name,
            fill=bar_text,
            font=title_font,
        )

    # Date (right side)
    date_str = datetime.now().strftime("%d-%m-%Y")
    bbox = draw.textbbox((0, 0), date_str, font=date_font)
    date_w = bbox[2] - bbox[0]
    date_x = PRINT_WIDTH - PADDING - date_w - 10
    date_y = content_y_center - 10
    draw.text(
        (date_x, date_y),
        date_str,
        fill=bar_text,
        font=date_font,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_and_fit(jpeg_data: bytes, max_w: int, max_h: int) -> Image.Image:
    """Load a JPEG and resize/crop to fit the target dimensions exactly.

    If the photo's aspect ratio doesn't match the target, it is
    center-cropped first, then resized.
    """
    img = Image.open(io.BytesIO(jpeg_data)).convert("RGB")
    w, h = img.size
    target_ratio = max_w / max_h

    # Center-crop to match target aspect ratio
    current_ratio = w / h
    if abs(current_ratio - target_ratio) > 0.01:
        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

    # Resize to exact target dimensions
    img = img.resize((max_w, max_h), Image.LANCZOS)
    return img


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font, falling back to Pillow's built-in."""
    if font_path:
        try:
            path = Path(font_path)
            if not path.is_absolute():
                path = Path.cwd() / path
            if path.exists():
                return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    # Fallback: try common system fonts, then Pillow default
    for fallback in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(fallback, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Convenience: get theme colors for branding bar
# ---------------------------------------------------------------------------

def get_theme_branding_colors(theme) -> dict:
    """Extract branding bar colors from a ThemeData object.

    Args:
        theme: A ThemeData instance from the theme system.

    Returns:
        Dict with hex color strings for the branding bar.
    """
    def rgba_to_hex(rgba: tuple) -> str:
        r, g, b = int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    return {
        "bar_background": rgba_to_hex(theme.colors.surface),
        "bar_text": rgba_to_hex(theme.colors.text),
        "bar_accent": rgba_to_hex(theme.colors.accent),
    }
