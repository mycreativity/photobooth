"""Internationalisation (i18n) support.

Translation strings are stored in human-editable TOML files under the
``locales/`` directory.  Each file is named by its language code
(e.g. ``nl.toml``, ``en.toml``).

Usage::

    from photobooth.i18n import translations
    t = translations.load("nl")
    print(t("idle.title"))        # → "Photobooth"
    print(t("idle.subtitle"))     # → "Tik op het scherm om te beginnen"
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


# Default search path for locale files (relative to project root)
_DEFAULT_LOCALES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "locales"


class Translations:
    """Flat key-value translation store loaded from a TOML file.

    Keys use dot-notation that mirrors the TOML table structure::

        [idle]
        title = "Photobooth"

    …is accessed as ``t("idle.title")``.
    """

    def __init__(self, data: dict[str, Any], language: str) -> None:
        self._language = language
        self._strings: dict[str, str] = {}
        self._flatten(data)

    @property
    def language(self) -> str:
        return self._language

    @property
    def keys(self) -> list[str]:
        """All available translation keys (sorted)."""
        return sorted(self._strings.keys())

    def __call__(self, key: str, **kwargs: str) -> str:
        """Look up a translation string by dotted key.

        Supports simple ``{placeholder}`` substitution via kwargs.
        Returns the key itself if no translation is found (makes missing
        translations visible without crashing).
        """
        value = self._strings.get(key, key)
        if kwargs:
            try:
                value = value.format(**kwargs)
            except KeyError:
                pass  # Return unformatted string rather than crash
        return value

    def has(self, key: str) -> bool:
        """Check if a translation key exists."""
        return key in self._strings

    def _flatten(self, data: dict[str, Any], prefix: str = "") -> None:
        """Recursively flatten nested TOML tables into dotted keys."""
        for k, v in data.items():
            full_key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
            if isinstance(v, dict):
                self._flatten(v, full_key)
            else:
                self._strings[full_key] = str(v)


def load(language: str, locales_dir: Path | None = None) -> Translations:
    """Load translations for a given language code.

    Args:
        language: ISO 639-1 code, e.g. ``"nl"`` or ``"en"``.
        locales_dir: Directory containing ``<lang>.toml`` files.
                     Defaults to the project's ``locales/`` directory.

    Returns:
        A ``Translations`` instance.

    Raises:
        FileNotFoundError: If the locale file doesn't exist.
    """
    directory = locales_dir or _DEFAULT_LOCALES_DIR
    locale_file = directory / f"{language}.toml"

    if not locale_file.exists():
        raise FileNotFoundError(
            f"Locale file not found: {locale_file}  "
            f"(available: {[f.stem for f in directory.glob('*.toml')]})"
        )

    with open(locale_file, "rb") as f:
        data = tomllib.load(f)

    return Translations(data, language=language)


def available_languages(locales_dir: Path | None = None) -> list[str]:
    """List all available language codes based on files in the locales dir."""
    directory = locales_dir or _DEFAULT_LOCALES_DIR
    if not directory.exists():
        return []
    return sorted(f.stem for f in directory.glob("*.toml"))
