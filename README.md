# Photobooth

Een touchscreen-photobooth applicatie voor de Raspberry Pi 4, gebouwd met Python en Kivy.

## Features

- 🎨 **Thema-systeem** — Visuele thema's met kleuren, typografie en animatie-instellingen. Eenvoudig nieuwe thema's toevoegen.
- 🌍 **Meertalig** — Nederlands (standaard) en Engels. Vertalingen in bewerkbare TOML-bestanden (`locales/`).
- 📸 **Camera-abstractie** — Protocol-gebaseerde camera-service met stub voor development en gphoto2 voor DSLR (Canon EOS 750D).
- 🖥️ **Live preview** — Achtergrondlaag voor camera-preview die achter alle schermen draait.
- 📱 **Multi-screen flow** — Idle → Countdown → Capture → Review → Print
- ⚙️ **TOML-configuratie** — Alle instellingen in `booth.toml`, geen code-aanpassingen nodig.

## Tech Stack

| Laag | Keuze | Waarom |
|------|-------|--------|
| Taal | Python 3.11+ | Beste DSLR + Pi ecosysteem |
| UI | Kivy | GPU-versneld, native touch, animaties |
| Camera | python-gphoto2 | Volledige 750D ondersteuning, live preview |
| Beeldverwerking | Pillow + OpenCV | Compositing + computer vision |
| Concurrency | threading + ProcessPoolExecutor | UI blijft altijd responsive |
| Printen | pycups | CUPS integratie |
| Opslag | SQLite + bestandssysteem | Simpel, betrouwbaar |
| Configuratie | TOML (stdlib) | Menselijk bewerkbaar |
| OS | Ubuntu 22.04 LTS 64-bit | Beste aarch64 ondersteuning |

## Projectstructuur

```
photobooth/
├── booth.toml                  # Applicatie-configuratie
├── locales/
│   ├── nl.toml                 # Nederlandse vertalingen
│   └── en.toml                 # Engelse vertalingen
├── src/
│   └── photobooth/
│       ├── __init__.py
│       ├── __main__.py         # Entry point
│       ├── app.py              # Kivy App subclass
│       ├── config.py           # TOML config → dataclasses
│       ├── i18n/
│       │   └── __init__.py     # Vertaalsysteem
│       ├── services/
│       │   ├── __init__.py
│       │   └── camera.py       # Camera protocol + stub
│       └── ui/
│           ├── __init__.py
│           ├── screens.py      # Screen management + flow
│           └── themes.py       # Thema-systeem
├── tests/
│   ├── test_camera.py
│   ├── test_config.py
│   ├── test_i18n.py
│   ├── test_screens.py
│   └── test_themes.py
└── pyproject.toml              # Project metadata + dependencies
```

## Installatie

### Development (macOS / Linux)

```bash
# Maak een virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Installeer in development mode met test-dependencies
pip install -e ".[dev]"
```

### Raspberry Pi 4

```bash
# Systeempakketten
sudo apt install python3-kivy python3-sdl2 libgphoto2-dev mesa-utils libgles2-mesa-dev

# Python packages
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[pi]"
```

## Gebruik

```bash
# Start de applicatie
python -m photobooth

# Of na installatie:
photobooth
```

## Configuratie

Alle instellingen staan in `booth.toml`:

```toml
[app]
name = "Photobooth"
fullscreen = false
language = "nl"        # "nl" of "en"
theme = "classic"

[camera]
backend = "stub"       # "stub" voor development, "gphoto2" voor DSLR
```

## Vertalingen

Vertalingen staan in `locales/<taalcode>.toml`. Nieuwe taal toevoegen:

1. Kopieer `locales/nl.toml` naar `locales/<code>.toml`
2. Vertaal alle waarden
3. Zet `language = "<code>"` in `booth.toml`

## Thema's

Thema's worden gedefinieerd in `src/photobooth/ui/themes.py`. Een thema bevat:
- **Kleuren** — achtergrond, accenten, tekst, overlay
- **Typografie** — lettertypes en -groottes
- **Animaties** — overgangstijden en easing

## Tests

```bash
# Alle tests
pytest

# Met coverage
pytest --cov=photobooth

# Specifieke module
pytest tests/test_config.py -v
```

## Licentie

MIT
