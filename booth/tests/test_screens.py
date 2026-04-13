"""Unit tests for the screen management system."""

import pytest

from photobooth.i18n import Translations
from photobooth.ui.screens import (
    BaseBoothScreen,
    LivePreviewLayer,
    OverlayLayer,
    SessionState,
    LAYOUT_SINGLE,
    LAYOUT_STRIP,
    LAYOUT_GRID,
    LAYOUT_PHOTO_COUNT,
    FILTER_NONE,
    SCREEN_FLOW,
    SCREEN_SPLASH,
    SCREEN_EVENT_REQUIRED,
    SCREEN_IDLE,
    SCREEN_LAYOUT,
    SCREEN_FILTER,
    SCREEN_COUNTDOWN,
    SCREEN_CAPTURE,
    SCREEN_REVIEW,
    SCREEN_DELIVER,
    SCREEN_PRINT,
    SCREEN_SETTINGS,
    SCREEN_REGISTRY,
    build_screen_manager,
)
from photobooth.ui.themes import THEME_CLASSIC


@pytest.fixture
def t():
    return Translations({"idle.title": "Test", "idle.subtitle": "Sub", "idle.tap_to_start": "START"}, "en")


@pytest.fixture
def theme():
    return THEME_CLASSIC


class TestScreenConstants:
    """Tests for screen name constants and flow."""

    def test_screen_flow_starts_with_splash(self):
        assert SCREEN_FLOW[0] == SCREEN_SPLASH

    def test_screen_flow_ends_with_print(self):
        assert SCREEN_FLOW[-1] == SCREEN_PRINT

    def test_screen_flow_has_ten_steps(self):
        assert len(SCREEN_FLOW) == 10

    def test_flow_includes_layout_filter_deliver(self):
        assert SCREEN_LAYOUT in SCREEN_FLOW
        assert SCREEN_FILTER in SCREEN_FLOW
        assert SCREEN_DELIVER in SCREEN_FLOW

    def test_all_flow_screens_in_registry(self):
        for name in SCREEN_FLOW:
            assert name in SCREEN_REGISTRY

    def test_settings_in_registry(self):
        assert SCREEN_SETTINGS in SCREEN_REGISTRY

    def test_registry_classes_extend_base(self):
        for cls in SCREEN_REGISTRY.values():
            assert issubclass(cls, BaseBoothScreen)


class TestScreenFlow:
    """Tests for the correct flow order."""

    def test_flow_order(self):
        expected = [
            SCREEN_SPLASH,
            SCREEN_EVENT_REQUIRED,
            SCREEN_IDLE,
            SCREEN_LAYOUT,
            SCREEN_FILTER,
            SCREEN_COUNTDOWN,
            SCREEN_CAPTURE,
            SCREEN_REVIEW,
            SCREEN_DELIVER,
            SCREEN_PRINT,
        ]
        assert SCREEN_FLOW == expected


class TestLayoutConstants:
    """Tests for layout options."""

    def test_single_is_one_photo(self):
        assert LAYOUT_PHOTO_COUNT[LAYOUT_SINGLE] == 1

    def test_strip_is_three_photos(self):
        assert LAYOUT_PHOTO_COUNT[LAYOUT_STRIP] == 3

    def test_grid_is_four_photos(self):
        assert LAYOUT_PHOTO_COUNT[LAYOUT_GRID] == 4


class TestFilterConstants:
    """Tests for filter presets."""

    def test_filter_none_value(self):
        assert FILTER_NONE == "none"


class TestSessionState:
    """Tests for the session state object."""

    def test_initial_state(self):
        s = SessionState()
        assert s.session_id is None
        assert s.event_id is None
        assert s.layout == LAYOUT_SINGLE
        assert s.filter == FILTER_NONE
        assert s.photos_needed == 1
        assert s.current_photo_seq == 1
        assert s.captured_photos == []
        assert s.retake_target is None
        assert s.polish_applied == {"retouch": False, "brightness": False, "glamour": False}

    def test_reset(self):
        s = SessionState()
        s.layout = LAYOUT_STRIP
        s.filter = "glamour_bw"
        s.photos_needed = 3
        s.current_photo_seq = 2
        s.captured_photos = [b"data"]
        s.session_id = 42
        s.retake_target = 1
        s.polish_applied = {"retouch": True, "brightness": True, "glamour": False}

        s.reset()
        assert s.session_id is None
        assert s.layout == LAYOUT_SINGLE
        assert s.photos_needed == 1
        assert s.captured_photos == []
        assert s.retake_target is None
        assert s.polish_applied == {"retouch": False, "brightness": False, "glamour": False}

    def test_retake_target_can_be_set(self):
        s = SessionState()
        s.retake_target = 2
        assert s.retake_target == 2

    def test_polish_applied_tracks_effects(self):
        s = SessionState()
        s.polish_applied["retouch"] = True
        assert s.polish_applied["retouch"] is True
        assert s.polish_applied["brightness"] is False
        assert s.polish_applied["glamour"] is False


class TestLivePreviewLayer:
    """Tests for the live preview layer."""

    def test_can_instantiate(self):
        layer = LivePreviewLayer()
        assert layer is not None

    def test_custom_bg_color(self):
        layer = LivePreviewLayer(bg_color=(1.0, 0.0, 0.0, 1.0))
        assert layer is not None

    def test_no_camera_preview_without_camera(self):
        layer = LivePreviewLayer()
        layer.start_camera_preview()
        assert not layer._camera_active


class TestOverlayLayer:
    """Tests for the overlay layer."""

    def test_can_instantiate(self):
        overlay = OverlayLayer(overlay_color=(0.0, 0.0, 0.0, 0.5))
        assert overlay is not None


class TestBuildScreenManager:
    """Tests for the root widget builder."""

    def test_returns_widget_with_children(self, t, theme):
        root = build_screen_manager(t=t, theme=theme)
        # Root is a FloatLayout with 3 children: preview + overlay + screen manager
        assert len(root.children) == 3

    def test_screen_manager_starts_on_splash(self, t, theme):
        root = build_screen_manager(t=t, theme=theme)
        sm = root.children[0]
        assert sm.current == SCREEN_SPLASH

    def test_all_screens_registered(self, t, theme):
        root = build_screen_manager(t=t, theme=theme)
        sm = root.children[0]
        screen_names = [s.name for s in sm.screens]
        for name in SCREEN_FLOW:
            assert name in screen_names
        assert SCREEN_SETTINGS in screen_names


class TestIdleScreen:
    """Tests for the idle screen."""

    def test_uses_translated_title(self, t, theme):
        root = build_screen_manager(t=t, theme=theme)
        sm = root.children[0]
        idle = sm.get_screen(SCREEN_IDLE)
        assert idle.t("idle.title") == "Test"
