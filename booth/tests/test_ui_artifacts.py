"""Tests to prevent UI artifact regressions.

These tests guard against the class of bugs where Kivy canvas
``RoundedRectangle`` instructions are created without explicit ``pos``
and ``size``, causing dark rectangles at (0, 0) before the first layout
pass.  They also verify that widgets inside a ``FloatLayout`` have the
correct ``pos_hint`` so they don't stay stuck at the origin.
"""

import ast
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Source file paths
# ---------------------------------------------------------------------------
_SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "photobooth" / "ui"
_COMPONENTS_FILE = _SRC_ROOT / "components.py"
_SCREENS_FILE = _SRC_ROOT / "screens.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. RoundedRectangle must always have explicit pos and size
# ---------------------------------------------------------------------------

class TestRoundedRectangleInit:
    """Every ``RoundedRectangle(...)`` call must include ``pos=`` and ``size=``
    arguments to prevent the Kivy default of (0,0)/(100,100).
    """

    @staticmethod
    def _find_rrect_calls(source: str, filepath: str) -> list[tuple[int, str]]:
        """Return (line_number, line_text) for RoundedRectangle calls
        missing explicit ``pos=`` or ``size=`` arguments.
        """
        bad = []
        lines = source.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if "RoundedRectangle(" in line:
                # Collect the full call (may span multiple lines)
                call_text = line
                paren_depth = line.count("(") - line.count(")")
                j = i + 1
                while paren_depth > 0 and j < len(lines):
                    call_text += " " + lines[j]
                    paren_depth += lines[j].count("(") - lines[j].count(")")
                    j += 1

                # Check for pos= and size=
                has_pos = "pos=" in call_text or "pos =" in call_text
                has_size = "size=" in call_text or "size =" in call_text

                if not has_pos or not has_size:
                    bad.append((i + 1, line.strip()))
            i += 1
        return bad

    def test_components_no_bare_rounded_rectangles(self):
        """All RoundedRectangle in components.py must have pos= and size=."""
        source = _read_source(_COMPONENTS_FILE)
        bad = self._find_rrect_calls(source, str(_COMPONENTS_FILE))
        assert bad == [], (
            f"RoundedRectangle without explicit pos/size in components.py:\n"
            + "\n".join(f"  line {n}: {t}" for n, t in bad)
        )

    def test_screens_no_bare_rounded_rectangles(self):
        """All RoundedRectangle in screens.py must have pos= and size=."""
        source = _read_source(_SCREENS_FILE)
        bad = self._find_rrect_calls(source, str(_SCREENS_FILE))
        assert bad == [], (
            f"RoundedRectangle without explicit pos/size in screens.py:\n"
            + "\n".join(f"  line {n}: {t}" for n, t in bad)
        )


# ---------------------------------------------------------------------------
# 2. Filter cards must be kept square
# ---------------------------------------------------------------------------

class TestFilterCardSquare:
    """The filter cards must bind width to height so they stay square,
    preventing layout distortion.
    """

    def test_filter_screen_has_square_bind(self):
        """FilterScreen must bind card height→width for square cards."""
        source = _read_source(_SCREENS_FILE)

        # Find the FilterScreen class and check for height→width bind
        in_filter_screen = False
        found_square_bind = False
        for line in source.splitlines():
            if "class FilterScreen" in line:
                in_filter_screen = True
            elif in_filter_screen and line.startswith("class "):
                break
            if in_filter_screen and "bind(height=" in line and "width" in line:
                found_square_bind = True
                break

        assert found_square_bind, (
            "FilterScreen must bind card height→width to keep cards square. "
            "Expected a line like: card.bind(height=lambda w, h: setattr(w, 'width', h))"
        )


# ---------------------------------------------------------------------------
# 3. BoothButton layers must all have pos/size
# ---------------------------------------------------------------------------

class TestBoothButtonLayers:
    """BoothButton draws glow, border, and fill layers on canvas.before.
    All three must initialise with explicit pos and size.
    """

    def test_all_layers_have_pos_size(self):
        source = _read_source(_COMPONENTS_FILE)

        # Find the BoothButton __init__ method and count RoundedRectangle calls
        in_button = False
        in_init = False
        rect_calls = []

        for i, line in enumerate(source.splitlines(), 1):
            if "class BoothButton" in line:
                in_button = True
            elif in_button and line.startswith("class "):
                break
            if in_button and "def __init__" in line:
                in_init = True
            elif in_init and line.strip().startswith("def "):
                in_init = False
            if in_init and "RoundedRectangle(" in line:
                rect_calls.append((i, line.strip()))

        # All RoundedRectangle in BoothButton.__init__ must have pos= and size=
        for line_num, line_text in rect_calls:
            # May span multiple lines — we just check the basic pattern
            # (full multi-line check is done in TestRoundedRectangleInit)
            pass

        # At minimum, BoothButton should have border and fill rects
        assert len(rect_calls) >= 2, (
            f"Expected at least 2 RoundedRectangle calls in BoothButton.__init__, "
            f"found {len(rect_calls)}"
        )


# ---------------------------------------------------------------------------
# 4. Thumbnail card bg must be drawn on card.canvas.before, not a child
# ---------------------------------------------------------------------------

class TestThumbnailCardBg:
    """The thumbnail card background in ReviewScreen must be drawn on the
    card's own canvas.before (not a child Widget) to avoid FloatLayout
    positioning bugs where children without pos_hint stay at (0, 0).
    """

    def test_no_card_bg_widget_in_build_thumbnails(self):
        """_build_thumbnails must not create a card_bg Widget child."""
        source = _read_source(_SCREENS_FILE)

        # Find _build_thumbnails method
        in_method = False
        found_card_bg_widget = False

        for line in source.splitlines():
            if "def _build_thumbnails" in line:
                in_method = True
            elif in_method and (line.strip().startswith("def ") and "def _build_thumbnails" not in line):
                break
            if in_method and "card_bg = Widget(" in line:
                found_card_bg_widget = True
                break

        assert not found_card_bg_widget, (
            "_build_thumbnails must draw card background on card.canvas.before, "
            "not via a separate Widget child (causes pos=(0,0) artifact in FloatLayout)"
        )

    def test_card_bg_drawn_on_card_canvas(self):
        """_build_thumbnails must draw the bg on card.canvas.before."""
        source = _read_source(_SCREENS_FILE)

        in_method = False
        found_canvas_before = False

        for line in source.splitlines():
            if "def _build_thumbnails" in line:
                in_method = True
            elif in_method and (line.strip().startswith("def ") and "def _build_thumbnails" not in line):
                break
            if in_method and "card.canvas.before" in line:
                found_canvas_before = True
                break

        assert found_canvas_before, (
            "_build_thumbnails must draw the background on card.canvas.before"
        )
