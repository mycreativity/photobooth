#!/usr/bin/env python3
"""LED worker — runs as root subprocess, reads commands from stdin.

This script is spawned by the main app via ``sudo python led_worker.py``
so the app itself doesn't need root.  Commands are single-line JSON.

Commands:
    {"cmd": "fill", "color": [r,g,b,w], "brightness": N}
    {"cmd": "stop"}
"""

import json
import math
import sys
import time

from rpi_ws281x import PixelStrip, Color, ws

LED_COUNT = 80
GPIO_PIN = 18
FREQ_HZ = 800000
DMA = 10
BRIGHTNESS = 80
CHANNEL = 0

strip = PixelStrip(LED_COUNT, GPIO_PIN, FREQ_HZ, DMA, False, BRIGHTNESS,
                   CHANNEL, ws.SK6812_STRIP_GRBW)
strip.begin()


def fill(r, g, b, w=0, brightness=None):
    if brightness is not None:
        strip.setBrightness(brightness)
    c = Color(r, g, b, w)
    for i in range(LED_COUNT):
        strip.setPixelColor(i, c)
    strip.show()


def fill_per_led(colors, brightness=None):
    """Set each LED individually. colors = list of [r,g,b,w]."""
    if brightness is not None:
        strip.setBrightness(brightness)
    for i, (r, g, b, w) in enumerate(colors):
        if i >= LED_COUNT:
            break
        strip.setPixelColor(i, Color(r, g, b, w))
    strip.show()


# Signal ready
print("READY", flush=True)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue

    cmd = msg.get("cmd")
    if cmd == "fill":
        c = msg.get("color", [0, 0, 0, 0])
        fill(*c, brightness=msg.get("brightness"))
        print("OK", flush=True)
    elif cmd == "fill_per_led":
        fill_per_led(msg.get("colors", []), brightness=msg.get("brightness"))
        print("OK", flush=True)
    elif cmd == "stop":
        fill(0, 0, 0, 0, brightness=0)
        print("OK", flush=True)
        break
    else:
        print("OK", flush=True)

# Cleanup
fill(0, 0, 0, 0, brightness=0)
