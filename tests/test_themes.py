"""Unit tests for the theme system."""

import pytest

from photobooth.ui.themes import (
    THEME_CLASSIC,
    AnimationStyle,
    ColorPalette,
    ThemeData,
    Typography,
    available_themes,
    get_theme,
    hex_to_rgba,
    register_theme,
)


class TestHexToRgba:
    """Tests for the hex colour conversion helper."""

    def test_six_digit_hex(self):
        r, g, b, a = hex_to_rgba("#FF0000")
        assert (r, g, b, a) == pytest.approx((1.0, 0.0, 0.0, 1.0))

    def test_eight_digit_hex_with_alpha(self):
        r, g, b, a = hex_to_rgba("#FF000080")
        assert r == pytest.approx(1.0)
        assert a == pytest.approx(128 / 255)

    def test_three_digit_hex(self):
        r, g, b, a = hex_to_rgba("#F00")
        assert (r, g, b, a) == pytest.approx((1.0, 0.0, 0.0, 1.0))

    def test_four_digit_hex_with_alpha(self):
        r, g, b, a = hex_to_rgba("#F008")
        assert r == pytest.approx(1.0)
        assert a == pytest.approx(0x88 / 255)

    def test_without_hash(self):
        result = hex_to_rgba("5B85F5")
        assert len(result) == 4
        assert result[3] == pytest.approx(1.0)

    def test_white(self):
        assert hex_to_rgba("#FFFFFF") == pytest.approx((1.0, 1.0, 1.0, 1.0))

    def test_black_transparent(self):
        r, g, b, a = hex_to_rgba("#00000000")
        assert (r, g, b, a) == pytest.approx((0.0, 0.0, 0.0, 0.0))

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="Invalid hex colour"):
            hex_to_rgba("#12345")

    def test_classic_theme_colors_are_valid_rgba(self):
        """Verify all classic theme colors were correctly converted from hex."""
        colors = THEME_CLASSIC.colors
        for field_name in ColorPalette.__dataclass_fields__:
            rgba = getattr(colors, field_name)
            assert len(rgba) == 4, f"{field_name} should be RGBA"
            assert all(0.0 <= v <= 1.0 for v in rgba), f"{field_name} values out of range"


class TestThemeData:
    """Tests for the ThemeData dataclass."""

    def test_classic_theme_exists(self):
        assert THEME_CLASSIC.name == "classic"
        assert THEME_CLASSIC.display_name == "Klassiek"

    def test_theme_is_immutable(self):
        with pytest.raises(AttributeError):
            THEME_CLASSIC.name = "hacked"  # type: ignore[misc]

    def test_color_palette_has_required_colors(self):
        colors = THEME_CLASSIC.colors
        assert len(colors.background) == 4  # RGBA
        assert len(colors.primary) == 4
        assert len(colors.text) == 4
        assert len(colors.overlay) == 4

    def test_typography_defaults(self):
        typo = Typography()
        assert typo.font_name == "Roboto"
        assert "sp" in typo.title_size

    def test_animation_defaults(self):
        anim = AnimationStyle()
        assert anim.transition_duration > 0
        assert anim.easing == "out_cubic"


class TestThemeRegistry:
    """Tests for the theme registry functions."""

    def test_classic_is_registered(self):
        theme = get_theme("classic")
        assert theme is THEME_CLASSIC

    def test_available_themes_includes_classic(self):
        themes = available_themes()
        assert "classic" in themes

    def test_unknown_theme_raises(self):
        with pytest.raises(KeyError, match="Unknown theme"):
            get_theme("nonexistent")

    def test_register_custom_theme(self):
        custom = ThemeData(name="test_custom", display_name="Test")
        register_theme(custom)
        assert get_theme("test_custom") is custom

        # Cleanup: remove from registry to avoid polluting other tests
        from photobooth.ui import themes
        del themes._themes["test_custom"]

    def test_register_overwrites_existing(self):
        original = get_theme("classic")
        replacement = ThemeData(name="classic", display_name="Replaced")
        register_theme(replacement)
        assert get_theme("classic").display_name == "Replaced"

        # Restore original
        register_theme(original)
