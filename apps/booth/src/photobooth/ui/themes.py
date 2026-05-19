"""Theme system for the photobooth UI.

A theme defines the visual identity of the booth: colours, typography,
overlay opacity, and animation style.  Themes are registered by name
and can be switched at runtime via configuration.

The system is designed for easy extension — to add a new theme, define
a ``ThemeData`` instance and register it with ``register_theme()``.

Colours are specified as hex strings (e.g. ``"#5B85F5"`` or ``"#00000073"``
for alpha) and converted to Kivy-compatible RGBA tuples internally.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def hex_to_rgba(hex_color: str) -> tuple[float, float, float, float]:
    """Convert a hex colour string to an RGBA tuple (0.0–1.0).

    Supported formats::

        "#RGB"        → 4-bit per channel, alpha = 1.0
        "#RGBA"       → 4-bit per channel including alpha
        "#RRGGBB"     → 8-bit per channel, alpha = 1.0
        "#RRGGBBAA"   → 8-bit per channel including alpha

    Args:
        hex_color: Hex colour string, with or without leading ``#``.

    Returns:
        A tuple of (r, g, b, a) with each value in the 0.0–1.0 range.

    Raises:
        ValueError: If the hex string has an unsupported length.
    """
    h = hex_color.lstrip("#")
    length = len(h)

    if length == 3:
        r, g, b = (int(c * 2, 16) / 255.0 for c in h)
        return (r, g, b, 1.0)
    elif length == 4:
        r, g, b, a = (int(c * 2, 16) / 255.0 for c in h)
        return (r, g, b, a)
    elif length == 6:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b, 1.0)
    elif length == 8:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        a = int(h[6:8], 16) / 255.0
        return (r, g, b, a)
    else:
        raise ValueError(
            f"Invalid hex colour {hex_color!r}: expected 3, 4, 6, or 8 hex digits."
        )


# Shorthand alias for use in theme definitions
c = hex_to_rgba


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColorPalette:
    """Core colour palette for a theme.

    All colours are RGBA tuples in 0.0–1.0 range (Kivy convention).
    Use ``hex_to_rgba()`` or its alias ``c()`` when defining palettes
    for readability.
    """

    background: tuple[float, ...] = c("#101418")
    surface: tuple[float, ...] = c("#1C2028")
    primary: tuple[float, ...] = c("#C29958")
    primary_light: tuple[float, ...] = c("#EDE8D0")
    secondary: tuple[float, ...] = c("#EDE8D0")
    accent: tuple[float, ...] = c("#C29958")
    accent_glow: tuple[float, ...] = c("#C2995866")
    text: tuple[float, ...] = c("#EDE8D0")
    text_muted: tuple[float, ...] = c("#EDE8D08C")
    overlay: tuple[float, ...] = c("#10141880")
    success: tuple[float, ...] = c("#83A2CC")
    error: tuple[float, ...] = c("#EB4848")


@dataclass(frozen=True)
class Typography:
    """Font sizing and family for a theme."""

    font_name: str = "Roboto"        # Kivy ships Roboto by default
    font_file: str = ""              # Path to TTF; empty = use Kivy built-in
    title_size: str = "48sp"
    subtitle_size: str = "22sp"
    body_size: str = "18sp"
    countdown_size: str = "120sp"
    button_size: str = "20sp"


@dataclass(frozen=True)
class AnimationStyle:
    """Animation timing presets."""

    transition_duration: float = 0.3     # Screen transitions
    fade_duration: float = 0.2           # Overlay fades
    countdown_scale: float = 1.4         # Scale pop on countdown digits
    easing: str = "out_cubic"            # Kivy animation transition name


@dataclass(frozen=True)
class ThemeData:
    """Complete theme definition."""

    name: str
    display_name: str
    colors: ColorPalette = field(default_factory=ColorPalette)
    typography: Typography = field(default_factory=Typography)
    animation: AnimationStyle = field(default_factory=AnimationStyle)
    overlay_image: str | None = None     # Optional branded overlay path
    countdown_sound: str | None = None   # Optional custom beep path


# ---------------------------------------------------------------------------
# Theme registry
# ---------------------------------------------------------------------------

_themes: dict[str, ThemeData] = {}


def register_theme(theme: ThemeData) -> None:
    """Register a theme by name. Overwrites if the name already exists."""
    _themes[theme.name] = theme


def get_theme(name: str) -> ThemeData:
    """Retrieve a registered theme by name.

    Raises:
        KeyError: If the theme name is not registered.
    """
    if name not in _themes:
        available = list(_themes.keys())
        raise KeyError(f"Unknown theme {name!r}. Available: {available}")
    return _themes[name]


def available_themes() -> list[str]:
    """Return a list of all registered theme names."""
    return sorted(_themes.keys())


# ---------------------------------------------------------------------------
# Built-in themes
# ---------------------------------------------------------------------------

THEME_CLASSIC = ThemeData(
    name="classic",
    display_name="Klassiek",
    colors=ColorPalette(
        background=c("#101418"),       # Neutral — near-black
        surface=c("#1C2028"),          # Slightly lighter surface
        primary=c("#C29958"),          # Primary — warm gold
        primary_light=c("#EDE8D0"),    # Secondary — cream
        secondary=c("#EDE8D0"),        # Secondary — cream
        accent=c("#C29958"),           # Gold CTA button
        accent_glow=c("#C2995866"),    # Gold glow effect
        text=c("#EDE8D0"),             # Cream text — high contrast
        text_muted=c("#EDE8D08C"),     # Cream text, dimmed
        overlay=c("#10141880"),        # Dark overlay
        success=c("#83A2CC"),          # Tertiary — muted blue
        error=c("#EB4747"),            # Keep red for errors
    ),
    typography=Typography(
        font_name="PlayfairDisplay",
        font_file="assets/fonts/PlayfairDisplay-Regular.ttf",
        title_size="48sp",
        subtitle_size="22sp",
        countdown_size="120sp",
    ),
    animation=AnimationStyle(
        transition_duration=0.3,
        countdown_scale=1.4,
        easing="out_cubic",
    ),
)

# Register all built-in themes on import
register_theme(THEME_CLASSIC)


def register_theme_fonts(theme: ThemeData) -> None:
    """Register a theme's custom font with Kivy.

    Call this once at app startup after selecting the active theme.
    If the theme uses a custom font_file, it is registered both under
    its own name AND as Kivy's default ``Roboto``, so all Label widgets
    automatically use the theme font.
    """
    from pathlib import Path
    font_file = theme.typography.font_file
    if not font_file:
        return  # Uses Kivy built-in font (e.g. Roboto)

    font_path = Path(font_file)
    if not font_path.is_absolute():
        font_path = Path.cwd() / font_path

    if not font_path.exists():
        import logging
        logging.getLogger(__name__).warning(
            "Font file not found: %s — falling back to Roboto", font_path,
        )
        return

    from kivy.core.text import LabelBase
    font_str = str(font_path)

    # Register under the theme's font name
    LabelBase.register(name=theme.typography.font_name, fn_regular=font_str)
    # Also override Kivy's default font so ALL Labels use it automatically
    LabelBase.register(name="Roboto", fn_regular=font_str)

    import logging
    logging.getLogger(__name__).info(
        "Registered font %r from %s", theme.typography.font_name, font_path,
    )
