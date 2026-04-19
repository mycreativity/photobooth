"""Print layout compositing engine.

Generates print-ready images at 300 DPI on a standard 10×15 cm photo
in portrait orientation.  Each layout arranges captured photos on a
canvas with a themed branding bar at the bottom.

All layout dimensions, slot positions, font sizes, and colors are
loaded from ``shared/card_layout.json`` — the single source of truth
shared with the admin dashboard.

Print dimensions::

    10 cm × 15 cm  →  1200 × 1800 px @ 300 DPI

Layout arrangements are defined as percentage-based slots in the
photo area (canvas minus branding bar).  See ``card_layout.json``
for the full definition.
"""

from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Load shared layout config
# ---------------------------------------------------------------------------

def _load_layout_config() -> dict[str, Any]:
    """Load card layout from shared config, with hardcoded fallback."""
    try:
        from shared.constants import load_card_layout
        return load_card_layout()
    except ImportError:
        pass

    # Direct file search fallback
    for path in [
        Path(__file__).resolve().parent.parent.parent.parent.parent / "shared" / "card_layout.json",
        Path("/opt/photobooth/shared/card_layout.json"),
    ]:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass

    logger.warning("card_layout.json not found — using hardcoded defaults")
    return _FALLBACK_CONFIG


# Hardcoded fallback (matches the original constants)
_FALLBACK_CONFIG: dict[str, Any] = {
    "canvas": {"width": 1200, "height": 1800},
    "photoRatio": 1.4,
    "padding": 30,
    "outputQuality": 95,
    "branding": {
        "heightPercent": 15,
        "accentLine": {"thickness": 3, "offsetTop": 8},
        "colors": {"background": "#1C2028", "text": "#EDE8D0", "accent": "#C29958"},
        "fonts": {"titleSize": 36, "titleBoldSize": 36, "dateSize": 22, "lineHeight": 42},
        "logo": {"maxWidth": 300, "maxHeight": 210, "paddingInner": 10},
    },
    "layouts": {
        "single": {"photosNeeded": 1, "slots": [{"x": 0, "y": 22.3, "w": 100, "h": 55.4}]},
        "strip": {
            "photosNeeded": 3,
            "slots": [
                {"x": 0, "y": 7.8, "w": 100, "h": 55.4},
                {"x": 0, "y": 65.2, "w": 48.7, "h": 26.9},
                {"x": 51.3, "y": 65.2, "w": 48.7, "h": 26.9},
            ],
        },
        "grid": {
            "photosNeeded": 4,
            "slots": [
                {"x": 0, "y": 22.0, "w": 48.7, "h": 26.9},
                {"x": 51.3, "y": 22.0, "w": 48.7, "h": 26.9},
                {"x": 0, "y": 51.0, "w": 48.7, "h": 26.9},
                {"x": 51.3, "y": 51.0, "w": 48.7, "h": 26.9},
            ],
        },
    },
}

# Load once at module level
_CFG = _load_layout_config()

# ---------------------------------------------------------------------------
# Derived constants (from config)
# ---------------------------------------------------------------------------

PRINT_WIDTH: int = _CFG["canvas"]["width"]
PRINT_HEIGHT: int = _CFG["canvas"]["height"]
PHOTO_RATIO: float = _CFG["photoRatio"]
PADDING: int = _CFG["padding"]
OUTPUT_QUALITY: int = _CFG["outputQuality"]

_branding = _CFG["branding"]
BRANDING_HEIGHT: int = int(PRINT_HEIGHT * _branding["heightPercent"] / 100)

# Photo area bounds
_PHOTO_AREA_TOP = PADDING
_PHOTO_AREA_BOTTOM = PRINT_HEIGHT - BRANDING_HEIGHT - PADDING
_PHOTO_AREA_HEIGHT = _PHOTO_AREA_BOTTOM - _PHOTO_AREA_TOP
_PHOTO_AREA_LEFT = PADDING
_PHOTO_AREA_RIGHT = PRINT_WIDTH - PADDING
_PHOTO_AREA_WIDTH = _PHOTO_AREA_RIGHT - _PHOTO_AREA_LEFT

# Branding bar styling
_ACCENT_THICKNESS: int = _branding["accentLine"]["thickness"]
_ACCENT_OFFSET: int = _branding["accentLine"]["offsetTop"]
_BAR_COLORS = _branding["colors"]
_FONTS = _branding["fonts"]
_LOGO = _branding["logo"]


# ---------------------------------------------------------------------------
# Event card config loader
# ---------------------------------------------------------------------------

def load_event_card_config() -> dict | None:
    """Load event card configuration from the local cache.

    The agent stores this at data/event_card.json when an event
    is pushed.

    Returns:
        Dict with event card config, or None if not available.
    """
    for path in [
        Path("/opt/photobooth/data/event_card.json"),
        Path("data/event_card.json"),
    ]:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception as e:
                logger.warning("Failed to load event card config: %s", e)
    return None


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
    background_image_path: str | None = None,
    branding_text: str | None = None,
    display_date: str | None = None,
) -> bytes:
    """Compose a print-ready image for the given layout.

    Args:
        layout: One of 'single', 'strip', 'grid'.
        photos: List of JPEG bytes (already cropped to 7:5).
        event_name: Event name for the branding bar.
        logo_path: Absolute path to the logo image file.
        theme_colors: Dict with 'primary', 'background', 'text' as hex strings.
        font_path: Path to TTF font file for branding text.
        background_image_path: Path to a background image (covers entire card).
        branding_text: Markdown-formatted text for branding strip.
        display_date: Human-readable date string (e.g. "Woensdag 15 April 2026").

    Returns:
        Composed print image as JPEG bytes (1200×1800 px).
    """
    # Try loading event card config if custom params not provided
    if not background_image_path and not branding_text:
        card_config = load_event_card_config()
        if card_config:
            background_image_path = background_image_path or card_config.get("background_image_path")
            branding_text = branding_text or card_config.get("branding_text")
            display_date = display_date or card_config.get("display_date")
            if not event_name:
                event_name = card_config.get("event_name", "")

    # Create canvas: use background image or white
    canvas = _create_canvas(background_image_path)

    # Place photos using slot definitions from config
    _place_photos(layout, photos, canvas)

    # Draw branding bar
    _draw_branding_bar(
        canvas, event_name, logo_path, theme_colors, font_path,
        branding_text=branding_text,
        display_date=display_date,
        has_background=background_image_path is not None,
    )

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=OUTPUT_QUALITY)
    result = buf.getvalue()

    logger.info(
        "[Print composite] layout=%s, %d photos, %d bytes, bg=%s",
        layout, len(photos), len(result),
        "custom" if background_image_path else "white",
    )
    return result


# ---------------------------------------------------------------------------
# Canvas creation
# ---------------------------------------------------------------------------

def _create_canvas(background_image_path: str | None = None) -> Image.Image:
    """Create the print canvas, optionally with a background image.

    The background image is resized to cover the full 1200×1800 canvas.
    """
    if background_image_path:
        try:
            bg_path = Path(background_image_path)
            if bg_path.exists():
                bg = Image.open(bg_path).convert("RGB")
                # Resize to cover canvas, center-cropping if needed
                bg = _cover_resize(bg, PRINT_WIDTH, PRINT_HEIGHT)
                return bg
        except Exception as e:
            logger.warning("Failed to load background image: %s", e)

    return Image.new("RGB", (PRINT_WIDTH, PRINT_HEIGHT), "white")


def _cover_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize image to cover the target dimensions (center-crop if needed)."""
    w, h = img.size
    target_ratio = target_w / target_h
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

    return img.resize((target_w, target_h), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Slot-based photo placement
# ---------------------------------------------------------------------------

def _place_photos(layout: str, photos: list[bytes], canvas: Image.Image) -> None:
    """Place photos on the canvas using slot definitions from config.

    Each slot is defined as percentages of the photo area:
    - x, y: top-left corner (0% = left/top of photo area)
    - w, h: width and height

    These are converted to absolute pixel coordinates for placement.
    """
    layouts = _CFG.get("layouts", {})
    layout_def = layouts.get(layout, layouts.get("single", {}))
    slots = layout_def.get("slots", [])

    for i, slot in enumerate(slots):
        if i >= len(photos) or not photos[i]:
            continue

        # Convert percentage to pixels within the photo area
        px_x = _PHOTO_AREA_LEFT + int(slot["x"] / 100 * _PHOTO_AREA_WIDTH)
        px_y = _PHOTO_AREA_TOP + int(slot["y"] / 100 * _PHOTO_AREA_HEIGHT)
        px_w = int(slot["w"] / 100 * _PHOTO_AREA_WIDTH)
        px_h = int(slot["h"] / 100 * _PHOTO_AREA_HEIGHT)

        photo = _load_and_fit(photos[i], px_w, px_h)

        # Center within the slot if the photo is smaller (due to aspect ratio)
        offset_x = (px_w - photo.width) // 2
        offset_y = (px_h - photo.height) // 2

        canvas.paste(photo, (px_x + offset_x, px_y + offset_y))


# ---------------------------------------------------------------------------
# Branding bar
# ---------------------------------------------------------------------------

def _draw_branding_bar(
    canvas: Image.Image,
    event_name: str,
    logo_path: str | None,
    theme_colors: dict | None = None,
    font_path: str | None = None,
    branding_text: str | None = None,
    display_date: str | None = None,
    has_background: bool = False,
) -> None:
    """Draw the branding bar at the bottom of the print.

    Layout: [Logo (left)] [Text (center)] [Date (right)]

    When a custom background is present, a semi-transparent dark
    overlay is drawn behind the bar for readability.
    """
    colors = theme_colors or {}
    bar_bg = colors.get("bar_background", _BAR_COLORS["background"])
    bar_text_color = colors.get("bar_text", _BAR_COLORS["text"])
    bar_accent = colors.get("bar_accent", _BAR_COLORS["accent"])

    bar_y = PRINT_HEIGHT - BRANDING_HEIGHT
    draw = ImageDraw.Draw(canvas)

    # Draw bar background — semi-transparent overlay when using custom bg
    if has_background:
        # Create a semi-transparent overlay for readability
        overlay = Image.new("RGBA", (PRINT_WIDTH, BRANDING_HEIGHT), (20, 24, 32, 200))
        canvas.paste(
            Image.composite(
                overlay.convert("RGB"),
                canvas.crop((0, bar_y, PRINT_WIDTH, PRINT_HEIGHT)),
                overlay.split()[3],
            ),
            (0, bar_y),
        )
    else:
        draw.rectangle(
            [0, bar_y, PRINT_WIDTH, PRINT_HEIGHT],
            fill=bar_bg,
        )

    # Reload draw after paste
    draw = ImageDraw.Draw(canvas)

    # Load fonts (sizes from config)
    title_font = _load_font(font_path, size=_FONTS["titleSize"])
    title_bold_font = _load_font(font_path, size=_FONTS["titleBoldSize"], bold=True)
    date_font = _load_font(font_path, size=_FONTS["dateSize"])

    # Accent line at top of bar
    line_y = bar_y + _ACCENT_OFFSET
    draw.rectangle(
        [PADDING, line_y, PRINT_WIDTH - PADDING, line_y + _ACCENT_THICKNESS],
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
                max_logo_h = _LOGO["maxHeight"]
                max_logo_w = _LOGO["maxWidth"]
                logo.thumbnail((max_logo_w, max_logo_h), Image.LANCZOS)

                # Auto-invert if the logo is dark on a dark background
                logo = _auto_invert_logo(logo)

                logo_x = PADDING + _LOGO["paddingInner"]
                logo_y = content_y_center - logo.height // 2
                canvas.paste(logo, (logo_x, logo_y), logo)
                logo_right_edge = logo_x + logo.width + 20
        except Exception as e:
            logger.warning("Failed to load logo: %s", e)

    # Text area (center)
    text_to_render = branding_text or event_name
    if text_to_render:
        text_area_left = max(logo_right_edge, PRINT_WIDTH // 4)
        text_area_right = PRINT_WIDTH - PADDING - 200  # Reserve space for date
        text_center_x = (text_area_left + text_area_right) // 2

        # Parse simple markdown and render
        _draw_markdown_text(
            draw, text_to_render,
            x_center=text_center_x,
            y=content_y_center - 20,
            regular_font=title_font,
            bold_font=title_bold_font,
            fill=bar_text_color,
        )

    # Date (right side)
    date_str = display_date or datetime.now().strftime("%d-%m-%Y")
    bbox = draw.textbbox((0, 0), date_str, font=date_font)
    date_w = bbox[2] - bbox[0]
    date_x = PRINT_WIDTH - PADDING - date_w - 10
    date_y = content_y_center - 10
    draw.text(
        (date_x, date_y),
        date_str,
        fill=bar_text_color,
        font=date_font,
    )


# ---------------------------------------------------------------------------
# Markdown rendering helpers
# ---------------------------------------------------------------------------

def _draw_markdown_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x_center: int,
    y: int,
    regular_font,
    bold_font,
    fill: str,
) -> None:
    """Render simple markdown (bold/italic) as PIL text.

    Supports **bold** and *italic* (rendered as bold for simplicity
    since italic requires a separate font file).

    Multi-line text is rendered with line breaks.
    """
    line_height = _FONTS["lineHeight"]
    lines = text.split("\n")
    total_height = len(lines) * line_height
    start_y = y - total_height // 2 + line_height // 2

    for i, line in enumerate(lines):
        line_y = start_y + i * line_height

        # Parse the line into segments: bold (**text**) and regular
        segments = _parse_markdown_line(line)

        # Calculate total width for centering
        total_w = 0
        for seg_text, is_bold in segments:
            font = bold_font if is_bold else regular_font
            bbox = draw.textbbox((0, 0), seg_text, font=font)
            total_w += bbox[2] - bbox[0]

        # Draw centered
        cursor_x = x_center - total_w // 2
        for seg_text, is_bold in segments:
            font = bold_font if is_bold else regular_font
            draw.text((cursor_x, line_y), seg_text, fill=fill, font=font)
            bbox = draw.textbbox((0, 0), seg_text, font=font)
            cursor_x += bbox[2] - bbox[0]


def _parse_markdown_line(line: str) -> list[tuple[str, bool]]:
    """Parse a line into segments of (text, is_bold).

    Handles **bold** and _italic_ markers.
    For simplicity, italic is treated the same as bold.
    """
    segments: list[tuple[str, bool]] = []
    # Pattern: **text** or __text__ or *text* or _text_
    pattern = r"(\*\*(.+?)\*\*|__(.+?)__|_(.+?)_|\*(.+?)\*)"
    last_end = 0

    for match in re.finditer(pattern, line):
        # Add text before this match
        if match.start() > last_end:
            segments.append((line[last_end:match.start()], False))

        # The matched bold/italic text
        bold_text = match.group(2) or match.group(3) or match.group(4) or match.group(5) or ""
        segments.append((bold_text, True))
        last_end = match.end()

    # Add remaining text
    if last_end < len(line):
        segments.append((line[last_end:], False))

    if not segments:
        segments.append((line, False))

    return segments


# ---------------------------------------------------------------------------
# Logo helpers
# ---------------------------------------------------------------------------

def _auto_invert_logo(logo: Image.Image) -> Image.Image:
    """Invert a logo if it appears dark (for use on dark backgrounds).

    Checks the average brightness of non-transparent pixels.
    If the logo is dark, inverts RGB channels while keeping alpha.
    """
    try:
        # Convert to RGBA if not already
        rgba = logo.convert("RGBA")
        pixels = list(rgba.getdata())

        # Calculate average brightness of non-transparent pixels
        total_brightness = 0
        count = 0
        for r, g, b, a in pixels:
            if a > 128:  # Only consider non-transparent pixels
                total_brightness += (r + g + b) / 3
                count += 1

        if count == 0:
            return logo

        avg_brightness = total_brightness / count

        # If logo is dark (avg brightness < 128), invert it
        if avg_brightness < 128:
            from PIL import ImageChops
            # Split channels
            r, g, b, a = rgba.split()
            rgb = Image.merge("RGB", (r, g, b))
            inverted = ImageChops.invert(rgb)
            # Recombine with original alpha
            ir, ig, ib = inverted.split()
            result = Image.merge("RGBA", (ir, ig, ib, a))
            return result
    except Exception as e:
        logger.debug("Logo invert check failed: %s", e)

    return logo


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


def _load_font(
    font_path: str | None,
    size: int,
    bold: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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
    if bold:
        bold_fonts = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for fallback in bold_fonts:
            try:
                return ImageFont.truetype(fallback, size)
            except Exception:
                continue

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
