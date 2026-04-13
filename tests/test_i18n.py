"""Unit tests for the i18n translation system."""

from pathlib import Path

import pytest

from photobooth.i18n import Translations, available_languages, load


# Path to the project's locale files
LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


class TestTranslations:
    """Tests for the Translations class."""

    def test_simple_lookup(self):
        t = Translations({"idle": {"title": "Hello"}}, language="en")
        assert t("idle.title") == "Hello"

    def test_missing_key_returns_key(self):
        t = Translations({}, language="en")
        assert t("nonexistent.key") == "nonexistent.key"

    def test_placeholder_substitution(self):
        t = Translations({"countdown": {"label": "{seconds}"}}, language="en")
        assert t("countdown.label", seconds="5") == "5"

    def test_placeholder_missing_kwarg_returns_unformatted(self):
        t = Translations({"msg": "Hello {name}"}, language="en")
        # No crash, returns the raw format string
        result = t("msg")
        assert "{name}" in result

    def test_language_property(self):
        t = Translations({}, language="nl")
        assert t.language == "nl"

    def test_has_key(self):
        t = Translations({"a": {"b": "value"}}, language="en")
        assert t.has("a.b") is True
        assert t.has("a.c") is False

    def test_keys_property_sorted(self):
        t = Translations({"z": "1", "a": {"b": "2", "a": "3"}}, language="en")
        assert t.keys == ["a.a", "a.b", "z"]

    def test_nested_flattening(self):
        data = {"level1": {"level2": {"level3": "deep"}}}
        t = Translations(data, language="en")
        assert t("level1.level2.level3") == "deep"

    def test_non_string_values_converted(self):
        t = Translations({"count": 42}, language="en")
        assert t("count") == "42"


class TestLoadFromFile:
    """Tests that load real locale TOML files."""

    def test_load_dutch(self):
        t = load("nl", locales_dir=LOCALES_DIR)
        assert t.language == "nl"
        assert t("idle.title") != "idle.title"  # Should be translated
        assert "Photobooth" in t("idle.title")

    def test_load_english(self):
        t = load("en", locales_dir=LOCALES_DIR)
        assert t.language == "en"
        assert "Tap" in t("idle.subtitle")

    def test_load_missing_language_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Locale file not found"):
            load("xx", locales_dir=tmp_path)

    def test_dutch_and_english_have_same_keys(self):
        nl = load("nl", locales_dir=LOCALES_DIR)
        en = load("en", locales_dir=LOCALES_DIR)
        assert nl.keys == en.keys, (
            f"Key mismatch!\n"
            f"  Only in NL: {set(nl.keys) - set(en.keys)}\n"
            f"  Only in EN: {set(en.keys) - set(nl.keys)}"
        )


class TestAvailableLanguages:
    """Tests for the available_languages helper."""

    def test_project_locales(self):
        langs = available_languages(LOCALES_DIR)
        assert "nl" in langs
        assert "en" in langs

    def test_empty_dir(self, tmp_path):
        assert available_languages(tmp_path) == []

    def test_nonexistent_dir(self):
        assert available_languages(Path("/nonexistent")) == []
