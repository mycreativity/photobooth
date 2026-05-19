# Photobooth op Raspberry Pi

## Wat je ziet bij het booten

**Niets.** Zwart scherm → photobooth app. Geen regenboog, geen tekst, geen login.

## Wat heb je nodig?

| Component | Aanbevolen |
|-----------|------------|
| **Raspberry Pi** | Pi 4 (4GB) of Pi 5 |
| **OS** | Raspberry Pi OS Bookworm 64-bit **Lite** |
| **Display** | 10.1" touchscreen (1280×800) |
| **Camera** | USB webcam of Canon DSLR (via gphoto2) |
| **SD-kaart** | 32GB+ |

## Vereisten op je Mac

```bash
# Installeer Ansible
brew install ansible

# Kopieer je SSH key naar de Pi (eenmalig)
ssh-copy-id pi@photobooth.local
```

## Eerste installatie

### 1. Flash Raspberry Pi OS Lite

Open **Raspberry Pi Imager** en configureer:
- **OS**: Raspberry Pi OS Lite (64-bit, Bookworm)
- **Hostname**: `photobooth`
- **SSH**: ✅ inschakelen
- **User**: `pi` / wachtwoord naar keuze
- **WiFi**: je netwerk

### 2. Draai de Ansible setup

```bash
cd apps/booth/ansible
ansible-playbook setup.yml
```

Dit duurt ~10 minuten en configureert alles:
- ✅ Systeempakketten (SDL2, OpenCV, libgphoto2, etc.)
- ✅ Python venv + app installatie
- ✅ Silent boot (geen tekst, geen login)
- ✅ Kiosk mode (fullscreen, geen cursor)
- ✅ Autostart via systemd
- ✅ GPU + camera configuratie

### 3. Reboot de Pi

```bash
ssh pi@photobooth.local sudo reboot
```

De Pi boot nu direct in de photobooth.

## Deployen

Code updaten naar de Pi? Eén commando:

```bash
cd apps/booth/ansible
ansible-playbook deploy.yml
```

Dit duurt ~10 seconden:
1. rsync code → Pi
2. pip install (nieuwe deps)
3. Service herstart

## Ansible structuur

```
ansible/
├── ansible.cfg          # Configuratie
├── inventory.ini        # Pi host + variabelen
├── setup.yml            # Volledige setup (eenmalig)
├── deploy.yml           # Code deploy (dagelijks)
└── templates/
    ├── photobooth.service.j2   # systemd service
    └── xinitrc.j2              # X11 kiosk sessie
```

## Specifieke taken draaien

```bash
# Alleen pakketten installeren
ansible-playbook setup.yml --tags packages

# Alleen silent boot configureren
ansible-playbook setup.yml --tags silent-boot

# Alleen de service updaten
ansible-playbook setup.yml --tags service

# Alleen kiosk mode
ansible-playbook setup.yml --tags kiosk
```

## Dagelijks beheer

| Actie | Commando |
|-------|----------|
| **Deployen** | `cd apps/booth/ansible && ansible-playbook deploy.yml` |
| **Logs** | `ssh pi@photobooth.local journalctl -u photobooth -f` |
| **Herstarten** | `ssh pi@photobooth.local sudo systemctl restart photobooth` |
| **Stoppen** | `ssh pi@photobooth.local sudo systemctl stop photobooth` |
| **Config aanpassen** | `ssh pi@photobooth.local nano /opt/photobooth/booth.toml` |
| **Foto's ophalen** | `scp -r pi@photobooth.local:/opt/photobooth/photos/ ./` |

## Boot sequence

```
Stroom aan → zwart scherm (5 sec) → photobooth fullscreen
```

Alles verborgen:
- ❌ Regenboog splash → `disable_splash=1`
- ❌ Pi logo → `logo.nologo`
- ❌ Kernel berichten → `quiet loglevel=0`
- ❌ Login prompt → `autologin + .hushlogin`
- ❌ Cursor → `unclutter + -nocursor`
- ❌ Screensaver → `xset s off`

## Troubleshooting

### App start niet
```bash
ssh pi@photobooth.local
journalctl -u photobooth --no-pager -n 50
```

### Inventory aanpassen (ander IP)
Bewerk `ansible/inventory.ini`:
```ini
booth  ansible_host=192.168.1.42  ansible_user=pi
```

### Webcam check
```bash
ssh pi@photobooth.local ls /dev/video*
```

### DSLR check
```bash
# Check of de camera zichtbaar is via USB
ssh pi@photobooth.local lsusb | grep Canon

# Check of gphoto2 de camera detecteert
ssh pi@photobooth.local /opt/photobooth/.venv/bin/python -c "import gphoto2 as gp; print(list(gp.Camera.autodetect()))"
```

> **Tip**: Zet de Canon op **M (Manual)** mode voor volledige softwarecontrole over belichting. Gebruik Settings → Camera → ⚡ Auto Belichting voor automatische kalibratie.

