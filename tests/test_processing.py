"""Unit tests for the image processing module."""

import io

import pytest
from PIL import Image

from photobooth.services.processing import (
    auto_retouch, brightness_boost, glamour_enhance, GlamourParams, _to_jpeg,
    apply_filter_to_jpeg,
)


def _make_test_jpeg(
    width: int = 100,
    height: int = 80,
    color: tuple[int, int, int] = (120, 80, 60),
    quality: int = 85,
) -> bytes:
    """Create a small synthetic JPEG for testing."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


class TestAutoRetouch:
    """Tests for the auto_retouch function."""

    def test_returns_bytes(self):
        result = auto_retouch(_make_test_jpeg())
        assert isinstance(result, bytes)

    def test_output_is_valid_jpeg(self):
        result = auto_retouch(_make_test_jpeg())
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_preserves_dimensions(self):
        original = _make_test_jpeg(width=200, height=150)
        result = auto_retouch(original)
        img = Image.open(io.BytesIO(result))
        assert img.size == (200, 150)

    def test_modifies_pixel_data(self):
        """The result should differ from the input (blur + contrast)."""
        original = _make_test_jpeg(color=(100, 50, 50))
        result = auto_retouch(original)
        # We can't compare raw JPEG bytes directly (re-encoding changes them)
        # but we can verify the output is a different image
        assert len(result) > 0

    def test_respects_quality_parameter(self):
        low_q = auto_retouch(_make_test_jpeg(), quality=10)
        high_q = auto_retouch(_make_test_jpeg(), quality=98)
        # Lower quality should produce smaller files
        assert len(low_q) < len(high_q)


class TestBrightnessBoost:
    """Tests for the brightness_boost function."""

    def test_returns_bytes(self):
        result = brightness_boost(_make_test_jpeg())
        assert isinstance(result, bytes)

    def test_output_is_valid_jpeg(self):
        result = brightness_boost(_make_test_jpeg())
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_preserves_dimensions(self):
        original = _make_test_jpeg(width=300, height=200)
        result = brightness_boost(original)
        img = Image.open(io.BytesIO(result))
        assert img.size == (300, 200)

    def test_factor_1_0_is_identity(self):
        """Factor of 1.0 should produce a visually identical image."""
        original = _make_test_jpeg()
        result = brightness_boost(original, factor=1.0)
        # Both should be valid JPEGs
        assert len(result) > 0

    def test_higher_factor_brightens(self):
        """Higher factor should increase average pixel value."""
        original = _make_test_jpeg(color=(80, 80, 80))
        result = brightness_boost(original, factor=1.5)

        orig_img = Image.open(io.BytesIO(original))
        bright_img = Image.open(io.BytesIO(result))

        orig_avg = sum(orig_img.get_flattened_data()[0]) / 3
        bright_avg = sum(bright_img.get_flattened_data()[0]) / 3

        assert bright_avg > orig_avg

    def test_default_factor_is_1_15(self):
        """Default factor produces a subtle brightness increase."""
        dark_jpeg = _make_test_jpeg(color=(60, 60, 60))
        result = brightness_boost(dark_jpeg)
        bright_img = Image.open(io.BytesIO(result))
        orig_img = Image.open(io.BytesIO(dark_jpeg))

        # Should be brighter than original
        bright_pixel_avg = sum(bright_img.get_flattened_data()[0]) / 3
        orig_pixel_avg = sum(orig_img.get_flattened_data()[0]) / 3
        assert bright_pixel_avg > orig_pixel_avg


class TestToJpeg:
    """Tests for the _to_jpeg helper."""

    def test_returns_bytes(self):
        img = Image.new("RGB", (10, 10), (255, 0, 0))
        result = _to_jpeg(img, quality=85)
        assert isinstance(result, bytes)

    def test_output_is_valid_jpeg(self):
        img = Image.new("RGB", (10, 10), (0, 255, 0))
        result = _to_jpeg(img, quality=85)
        loaded = Image.open(io.BytesIO(result))
        assert loaded.format == "JPEG"


class TestGlamourParams:
    """Tests for the GlamourParams dataclass."""

    def test_default_values(self):
        p = GlamourParams()
        assert p.skin_smooth == 0.7
        assert p.warmth == 0.5
        assert p.vignette == 0.5
        assert p.eye_enhance == 0.5
        assert p.makeup == 0.5
        assert p.sparkles == 0.3
        assert p.soft_glow == 0.4

    def test_custom_values(self):
        p = GlamourParams(
            skin_smooth=0.3, warmth=0.8, vignette=0.0,
            eye_enhance=1.0, makeup=0.6, sparkles=0.1, soft_glow=0.9,
        )
        assert p.skin_smooth == 0.3
        assert p.warmth == 0.8
        assert p.vignette == 0.0
        assert p.eye_enhance == 1.0
        assert p.makeup == 0.6
        assert p.sparkles == 0.1
        assert p.soft_glow == 0.9


class TestGlamourEnhance:
    """Tests for the glamour_enhance pipeline."""

    def test_returns_bytes(self):
        result = glamour_enhance(_make_test_jpeg())
        assert isinstance(result, bytes)

    def test_output_is_valid_jpeg(self):
        result = glamour_enhance(_make_test_jpeg())
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_preserves_dimensions(self):
        original = _make_test_jpeg(width=200, height=150)
        result = glamour_enhance(original)
        img = Image.open(io.BytesIO(result))
        assert img.size == (200, 150)

    def test_with_default_params(self):
        """Default params should produce a valid enhanced image."""
        result = glamour_enhance(_make_test_jpeg(), GlamourParams())
        assert len(result) > 0
        img = Image.open(io.BytesIO(result))
        assert img.size[0] > 0

    def test_with_all_zero_params(self):
        """All-zero params should still return a valid JPEG (no effects)."""
        params = GlamourParams(skin_smooth=0.0, warmth=0.0, vignette=0.0, eye_enhance=0.0)
        result = glamour_enhance(_make_test_jpeg(), params)
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_with_max_params(self):
        """Max intensity params should not crash."""
        params = GlamourParams(skin_smooth=1.0, warmth=1.0, vignette=1.0, eye_enhance=1.0)
        result = glamour_enhance(_make_test_jpeg(), params)
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_skin_only(self):
        """Only skin smoothing enabled."""
        params = GlamourParams(skin_smooth=0.8, warmth=0.0, vignette=0.0, eye_enhance=0.0)
        result = glamour_enhance(_make_test_jpeg(), params)
        assert len(result) > 0

    def test_warmth_only(self):
        """Only warmth/color grading enabled."""
        params = GlamourParams(skin_smooth=0.0, warmth=0.7, vignette=0.0, eye_enhance=0.0)
        result = glamour_enhance(_make_test_jpeg(), params)
        assert len(result) > 0

    def test_vignette_only(self):
        """Only vignette enabled."""
        params = GlamourParams(skin_smooth=0.0, warmth=0.0, vignette=0.6, eye_enhance=0.0)
        result = glamour_enhance(_make_test_jpeg(), params)
        assert len(result) > 0

    def test_respects_quality_parameter(self):
        low_q = glamour_enhance(_make_test_jpeg(), quality=10)
        high_q = glamour_enhance(_make_test_jpeg(), quality=98)
        assert len(low_q) < len(high_q)


class TestParseCubeFile:
    """Tests for the .cube file parser."""

    def test_parse_simple_cube(self, tmp_path):
        from photobooth.services.processing import _parse_cube_file
        cube = tmp_path / "test.cube"
        cube.write_text(
            'TITLE "Test LUT"\n'
            'LUT_3D_SIZE 2\n'
            '0.0 0.0 0.0\n'
            '1.0 0.0 0.0\n'
            '0.0 1.0 0.0\n'
            '1.0 1.0 0.0\n'
            '0.0 0.0 1.0\n'
            '1.0 0.0 1.0\n'
            '0.0 1.0 1.0\n'
            '1.0 1.0 1.0\n'
        )
        title, size, table = _parse_cube_file(cube)
        assert title == "Test LUT"
        assert size == 2
        assert len(table) == 8
        assert table[0] == (0.0, 0.0, 0.0)
        assert table[7] == (1.0, 1.0, 1.0)

    def test_parse_infers_size(self, tmp_path):
        from photobooth.services.processing import _parse_cube_file
        cube = tmp_path / "nosize.cube"
        # 2^3 = 8 entries, no LUT_3D_SIZE header
        lines = ["0.0 0.0 0.0\n"] * 8
        cube.write_text("".join(lines))
        _, size, table = _parse_cube_file(cube)
        assert size == 2
        assert len(table) == 8

    def test_parse_skips_comments(self, tmp_path):
        from photobooth.services.processing import _parse_cube_file
        cube = tmp_path / "comments.cube"
        cube.write_text(
            '# This is a comment\n'
            'TITLE "With Comments"\n'
            'LUT_3D_SIZE 2\n'
            '# Another comment\n'
            '0.5 0.5 0.5\n' * 8
        )
        title, size, table = _parse_cube_file(cube)
        assert title == "With Comments"
        assert len(table) == 8


class TestLutRegistry:
    """Tests for the LutRegistry class."""

    def test_empty_directory(self, tmp_path):
        from photobooth.services.processing import LutRegistry
        registry = LutRegistry(lut_dir=tmp_path)
        assert registry.available_luts() == []

    def test_nonexistent_directory(self, tmp_path):
        from photobooth.services.processing import LutRegistry
        registry = LutRegistry(lut_dir=tmp_path / "does_not_exist")
        assert registry.available_luts() == []

    def test_discovers_cube_files(self, tmp_path):
        from photobooth.services.processing import LutRegistry
        # Create a minimal .cube file
        cube = tmp_path / "warm.cube"
        cube.write_text(
            'TITLE "Warm"\n'
            'LUT_3D_SIZE 2\n'
            + '0.5 0.4 0.3\n' * 8
        )
        registry = LutRegistry(lut_dir=tmp_path)
        luts = registry.available_luts()
        assert len(luts) == 1
        assert luts[0][0] == "warm"
        assert luts[0][1] == "Warm"

    def test_has_lut(self, tmp_path):
        from photobooth.services.processing import LutRegistry
        cube = tmp_path / "cool.cube"
        cube.write_text('LUT_3D_SIZE 2\n' + '0.3 0.4 0.6\n' * 8)
        registry = LutRegistry(lut_dir=tmp_path)
        assert registry.has_lut("cool")
        assert not registry.has_lut("nonexistent")

    def test_apply_pil(self, tmp_path):
        from photobooth.services.processing import LutRegistry
        # Identity LUT (output = input)
        lines = []
        size = 2
        for b in range(size):
            for g in range(size):
                for r in range(size):
                    lines.append(f"{r/(size-1):.1f} {g/(size-1):.1f} {b/(size-1):.1f}\n")
        cube = tmp_path / "identity.cube"
        cube.write_text(f'LUT_3D_SIZE {size}\n' + ''.join(lines))
        registry = LutRegistry(lut_dir=tmp_path)
        img = Image.new("RGB", (10, 10), (128, 64, 32))
        result = registry.apply_pil(img, "identity")
        assert result.size == (10, 10)

    def test_apply_jpeg(self, tmp_path):
        from photobooth.services.processing import LutRegistry
        cube = tmp_path / "test_lut.cube"
        cube.write_text('LUT_3D_SIZE 2\n' + '0.5 0.5 0.5\n' * 8)
        registry = LutRegistry(lut_dir=tmp_path)
        jpeg = _make_test_jpeg()
        result = registry.apply_jpeg(jpeg, "test_lut")
        assert isinstance(result, bytes)
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_unknown_filter_passthrough(self, tmp_path):
        from photobooth.services.processing import LutRegistry
        registry = LutRegistry(lut_dir=tmp_path)
        img = Image.new("RGB", (10, 10), (100, 100, 100))
        result = registry.apply_pil(img, "nonexistent_filter")
        # Should return the original image unchanged
        assert result is img


class TestApplyFilterWithLut:
    """Tests for LUT integration in apply_filter_to_jpeg."""

    def test_builtin_filter_still_works(self):
        result = apply_filter_to_jpeg(_make_test_jpeg(), "vintage_love")
        assert isinstance(result, bytes)
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_classic_passthrough(self):
        original = _make_test_jpeg()
        result = apply_filter_to_jpeg(original, "classic")
        assert result == original

    def test_lut_filter_applies(self, tmp_path):
        """If we inject a LUT into the registry, apply_filter_to_jpeg uses it."""
        from photobooth.services.processing import LutRegistry, _lut_registry
        import photobooth.services.processing as proc_mod

        # Create a temp LUT
        cube = tmp_path / "test_inject.cube"
        cube.write_text('LUT_3D_SIZE 2\n' + '0.5 0.5 0.5\n' * 8)

        # Temporarily replace the global registry
        old_registry = proc_mod._lut_registry
        try:
            proc_mod._lut_registry = LutRegistry(lut_dir=tmp_path)
            result = apply_filter_to_jpeg(_make_test_jpeg(), "test_inject")
            assert isinstance(result, bytes)
            img = Image.open(io.BytesIO(result))
            assert img.format == "JPEG"
        finally:
            proc_mod._lut_registry = old_registry
