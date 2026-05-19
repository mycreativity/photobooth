"""Booth Agent — WebSocket client connecting to the admin server.

Runs as a background thread alongside the Kivy main loop.
Handles:
- Registration with the server
- Periodic heartbeats (CPU %, camera status, uptime, power usage)
- Receiving commands (start/stop preview, update settings, restart)
- Reconnection with exponential backoff
"""
import asyncio
import json
import logging
import os
import platform
import re
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Max log lines buffered (sent on next heartbeat if WS is down)
_LOG_BUFFER_SIZE = 200


class BoothAgent:
    """Persistent WebSocket connection to the admin server."""

    def __init__(self, config: dict, storage=None):
        self._config = config
        self._storage = storage  # StorageService for upload queue (AC1)
        self._url = config.get("url", "ws://localhost:8000")
        self._booth_id = config.get("booth_id", f"booth-{platform.node()}")
        self._booth_name = config.get("booth_name", platform.node())
        self._heartbeat_interval = config.get("heartbeat_interval", 10)
        self._reconnect_delay = config.get("reconnect_delay", 5)
        self._reconnect_max_delay = config.get("reconnect_max_delay", 60)

        self._ws = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._start_time = time.monotonic()

        # Server-assigned event info (received on registration)
        self.server_event_id: str = ""
        self.server_event_uid: str = ""

        # Callbacks for commands from server
        self._command_handlers: dict[str, callable] = {}

    def on_command(self, command: str, handler: callable):
        """Register a handler for a server command.

        Example::

            agent.on_command("start_preview", lambda msg: camera.start())
        """
        self._command_handlers[command] = handler

    def start(self):
        """Start the agent in a background thread."""
        if self._running:
            return
        self._running = True

        # Install log handler that forwards to WS
        self._log_handler = _WSLogHandler(self)
        self._log_handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(self._log_handler)

        self._thread = threading.Thread(
            target=self._run_loop,
            name="booth-agent",
            daemon=True,
        )
        self._thread.start()
        logger.info("Booth agent started → %s (booth_id=%s)", self._url, self._booth_id)

    def stop(self):
        """Stop the agent."""
        self._running = False
        # Remove log handler
        if hasattr(self, '_log_handler'):
            logging.getLogger().removeHandler(self._log_handler)
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Booth agent stopped")

    def _run_loop(self):
        """Run the async event loop in the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            logger.error("Agent loop error: %s", e)
        finally:
            self._loop.close()

    async def _connect_loop(self):
        """Connect to server with exponential backoff reconnection."""
        delay = self._reconnect_delay

        while self._running:
            try:
                await self._connect()
                delay = self._reconnect_delay  # Reset on successful connection
            except Exception as e:
                logger.warning("Connection failed: %s — retrying in %ds", e, delay)

            if not self._running:
                break

            await asyncio.sleep(delay)
            delay = min(delay * 2, self._reconnect_max_delay)

    async def _connect(self):
        """Establish WebSocket connection and handle messages."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed — agent disabled")
            self._running = False
            return

        # AC2: Don't put API key in URL — send in register message
        ws_url = f"{self._url}/ws/booth/{self._booth_id}"
        logger.info("Connecting to %s ...", ws_url)

        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
            self._ws = ws
            logger.info("Connected to server")

            # AC2: Send registration with API key in message body
            await ws.send(json.dumps({
                "type": "register",
                "booth_id": self._booth_id,
                "name": self._booth_name,
                "version": "0.1.0",
                "api_key": self._config.get("api_key", ""),
            }))

            # Start heartbeat task and upload retry queue
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))
            retry_task = asyncio.create_task(self._retry_queue_loop())

            try:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    msg_type = msg.get("type", "")
                    logger.debug("Server → booth: %s", msg_type)

                    if msg_type == "ack":
                        logger.info("Server ACK: %s", msg.get("status"))
                        # Store server event info if provided
                        if msg.get("event_id"):
                            self.server_event_id = msg["event_id"]
                            self.server_event_uid = msg.get("event_uid", "")
                            logger.info("Server event: id=%s uid=%s", self.server_event_id, self.server_event_uid)
                    elif msg_type == "update_settings":
                        self._handle_update_settings(msg.get("settings", {}))
                    elif msg_type == "push_event":
                        asyncio.create_task(self._handle_push_event(msg.get("event", {})))
                    elif msg_type == "restart":
                        self._handle_restart()
                    elif msg_type in self._command_handlers:
                        try:
                            self._command_handlers[msg_type](msg)
                        except Exception as e:
                            logger.error("Command handler error (%s): %s", msg_type, e)
                    else:
                        logger.debug("Unhandled message type: %s", msg_type)
            finally:
                heartbeat_task.cancel()
                retry_task.cancel()
                self._ws = None

    async def _heartbeat_loop(self, ws):
        """Send periodic heartbeats to the server."""
        while True:
            try:
                heartbeat = {
                    "type": "heartbeat",
                    **self._get_system_info(),
                }
                await ws.send(json.dumps(heartbeat))
                logger.debug("Heartbeat sent")
            except Exception as e:
                logger.warning("Heartbeat failed: %s", e)
                break
            await asyncio.sleep(self._heartbeat_interval)

    def _handle_update_settings(self, settings: dict) -> None:
        """Update booth.toml with new settings from admin.

        Keys map to TOML sections:
        - event_name → [app].event_name
        - language → [app].language
        - theme → [app].theme
        - first_countdown → [countdown].first_countdown
        - between_shots → [countdown].between_shots
        - camera_backend → [camera].backend
        - camera_iso → [camera].iso
        - camera_aperture → [camera].aperture
        - camera_shutter → [camera].shutter_speed
        - led_enabled → [led].enabled
        - led_brightness → [led].brightness
        """
        if not settings:
            return

        toml_path = Path("/opt/photobooth/booth.toml")
        if not toml_path.exists():
            toml_path = Path("booth.toml")
        if not toml_path.exists():
            logger.error("Cannot find booth.toml to update")
            return

        try:
            import tomllib
            with open(toml_path, "rb") as f:
                cfg = tomllib.load(f)
        except Exception as e:
            logger.error("Failed to read booth.toml: %s", e)
            return

        # Map flat keys to TOML structure
        key_map = {
            "event_name": ("app", "event_name"),
            "language": ("app", "language"),
            "theme": ("app", "theme"),
            "first_countdown": ("countdown", "first_countdown"),
            "between_shots": ("countdown", "between_shots"),
            "camera_backend": ("camera", "backend"),
            "camera_iso": ("camera", "iso"),
            "camera_aperture": ("camera", "aperture"),
            "camera_shutter": ("camera", "shutter_speed"),
            "led_enabled": ("led", "enabled"),
            "led_brightness": ("led", "brightness"),
        }

        changed = []
        for key, value in settings.items():
            if key in key_map:
                section, field = key_map[key]
                if section not in cfg:
                    cfg[section] = {}
                old = cfg[section].get(field)
                cfg[section][field] = value
                if old != value:
                    changed.append(f"{section}.{field}: {old} → {value}")

        if not changed:
            logger.info("No settings changed")
            return

        # Write back using toml format (manual, preserves structure)
        self._write_toml(toml_path, cfg)
        logger.info("Settings updated: %s", "; ".join(changed))

    def _write_toml(self, path: Path, cfg: dict) -> None:
        """Write a dict back to TOML format."""
        lines = []
        # Write top-level keys first (unlikely but handle gracefully)
        for key, value in cfg.items():
            if not isinstance(value, dict):
                lines.append(f"{key} = {self._toml_value(value)}")
        if lines:
            lines.append("")

        # Write sections
        for section, values in cfg.items():
            if isinstance(values, dict):
                lines.append(f"[{section}]")
                for key, value in values.items():
                    lines.append(f"{key} = {self._toml_value(value)}")
                lines.append("")

        path.write_text("\n".join(lines))

    @staticmethod
    def _toml_value(v) -> str:
        """Format a Python value as TOML."""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return str(v)
        if isinstance(v, str):
            return f'"{v}"'
        return f'"{v}"'

    def _handle_restart(self) -> None:
        """Restart the booth app process."""
        import sys
        logger.info("Remote restart requested by admin")
        # Give a moment for the log to be sent
        time.sleep(0.5)
        os.execv(sys.executable, [sys.executable, "-m", "photobooth"])

    async def _handle_push_event(self, event_data: dict) -> None:
        """Handle push_event from server: download background & cache config.

        The event card configuration is stored as a local JSON file
        so the booth can render photo cards without further API calls.
        """
        if not event_data:
            logger.warning("push_event received with empty data")
            return

        logger.info(
            "Received event card config: %s (bg=%s)",
            event_data.get("event_name", "?"),
            event_data.get("background_image", "none"),
        )

        # Determine data directory
        data_dir = Path("/opt/photobooth/data")
        if not data_dir.exists():
            data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)

        # Download background image if URL provided
        bg_url = event_data.get("background_url")
        local_bg_path = None
        if bg_url:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(bg_url) as resp:
                        if resp.status == 200:
                            bg_data = await resp.read()
                            # Use a fixed filename (overwritten each push)
                            local_bg_path = str(data_dir / "event_background.png")
                            Path(local_bg_path).write_bytes(bg_data)
                            logger.info(
                                "Background downloaded: %s (%d bytes)",
                                local_bg_path, len(bg_data),
                            )
                        else:
                            logger.warning("Background download failed: HTTP %d", resp.status)
            except Exception as e:
                logger.error("Failed to download background: %s", e)

        # Store event card config as JSON
        card_config = {
            "event_uid": event_data.get("event_uid", ""),
            "event_name": event_data.get("event_name", ""),
            "display_date": event_data.get("display_date", ""),
            "branding_text": event_data.get("branding_text", ""),
            "background_image_path": local_bg_path,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        config_path = data_dir / "event_card.json"
        config_path.write_text(json.dumps(card_config, indent=2))
        logger.info("Event card config saved to %s", config_path)

        # Notify registered handler (e.g. to update print settings)
        if "push_event" in self._command_handlers:
            try:
                self._command_handlers["push_event"](card_config)
            except Exception as e:
                logger.error("push_event callback error: %s", e)

    async def _upload_photo(
        self,
        file_path: str,
        event_id: str = "",
        session_id: str = "",
        seq: int = 1,
        variant: str = "final",
        _from_queue: bool = False,
    ) -> dict | None:
        """Upload a single photo to the server via HTTP POST.

        On failure, enqueues the photo for retry (AC1) unless it was
        already called from the retry queue.
        """
        import aiohttp

        path = Path(file_path)
        if not path.exists():
            logger.warning("Upload skipped — file not found: %s", file_path)
            return None

        # Convert WS URL to HTTP
        http_url = self._url.replace("ws://", "http://").replace("wss://", "https://")
        upload_url = f"{http_url}/api/photos/upload"

        try:
            data = aiohttp.FormData()
            data.add_field("file", path.read_bytes(),
                          filename=path.name,
                          content_type="image/jpeg")
            data.add_field("event_id", event_id)
            data.add_field("booth_id", self._booth_id)
            data.add_field("session_id", session_id)
            data.add_field("seq", str(seq))
            data.add_field("variant", variant)

            async with aiohttp.ClientSession() as session:
                async with session.post(upload_url, data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.info("Photo uploaded: %s → %s", path.name, result.get("filename"))
                        return result
                    else:
                        body = await resp.text()
                        logger.error("Upload failed (%d): %s", resp.status, body[:200])
                        # AC1: Enqueue for retry on failure (unless already from queue)
                        if not _from_queue and self._storage:
                            self._storage.enqueue_upload(
                                file_path=file_path,
                                event_id=event_id,
                                session_id=session_id,
                                seq=seq,
                                variant=variant,
                            )
                        return None
        except Exception as e:
            logger.error("Upload error: %s", e)
            # AC1: Enqueue for retry on failure (unless already from queue)
            if not _from_queue and self._storage:
                self._storage.enqueue_upload(
                    file_path=file_path,
                    event_id=event_id,
                    session_id=session_id,
                    seq=seq,
                    variant=variant,
                )
            return None

    async def _retry_queue_loop(self):
        """Poll the upload queue every 10s and retry failed uploads (AC1)."""
        while True:
            await asyncio.sleep(10)
            if not self._storage:
                continue
            try:
                pending = self._storage.get_pending_uploads(limit=5)
                for entry in pending:
                    result = await self._upload_photo(
                        file_path=entry["file_path"],
                        event_id=entry.get("event_id", ""),
                        session_id=entry.get("session_id", ""),
                        seq=entry.get("seq", 1),
                        variant=entry.get("variant", "final"),
                        _from_queue=True,
                    )
                    if result:
                        self._storage.dequeue_upload(entry["id"])
                        logger.info("Queue upload succeeded: %s", entry["file_path"])
                    else:
                        self._storage.increment_retries(entry["id"])
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Retry queue error: %s", e)

    def upload_photos(self, photos: list[dict]) -> None:
        """Queue photo uploads to the server (thread-safe).

        Each dict should have: file_path, event_id, session_id, seq, variant.
        Called from the Kivy main thread after a session completes.
        """
        if not self._loop or not self._running:
            logger.warning("Agent not running — skipping photo upload")
            return

        async def _do_uploads():
            for photo in photos:
                await self._upload_photo(
                    file_path=photo["file_path"],
                    event_id=photo.get("event_id", ""),
                    session_id=photo.get("session_id", ""),
                    seq=photo.get("seq", 1),
                    variant=photo.get("variant", "final"),
                )

        try:
            self._loop.call_soon_threadsafe(
                asyncio.ensure_future,
                _do_uploads(),
            )
        except RuntimeError:
            pass

    def _get_system_info(self) -> dict:
        """Collect full system metrics."""
        info = {
            "cpu": self._get_cpu_percent(),
            "cam_connected": self._is_camera_connected(),
            "uptime": int(time.monotonic() - self._start_time),
            "mem_total_mb": 0,
            "mem_used_mb": 0,
            "mem_percent": 0,
            "cpu_temp": None,
            "disk_total_gb": 0,
            "disk_used_gb": 0,
            "disk_free_gb": 0,
            "disk_percent": 0,
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            # Power / electricity
            "power_voltage": None,
            "power_current_a": None,
            "power_watts": None,
            "power_throttled": None,
        }

        # Memory
        try:
            with open("/proc/meminfo") as f:
                meminfo = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
                total = meminfo.get("MemTotal", 0)
                available = meminfo.get("MemAvailable", 0)
                info["mem_total_mb"] = total // 1024
                info["mem_used_mb"] = (total - available) // 1024
                info["mem_percent"] = round((total - available) / max(total, 1) * 100)
        except Exception:
            pass

        # CPU temperature
        try:
            temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
            if temp_path.exists():
                info["cpu_temp"] = round(int(temp_path.read_text().strip()) / 1000, 1)
        except Exception:
            pass

        # Disk usage
        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            info["disk_total_gb"] = round(total / (1024**3), 1)
            info["disk_used_gb"] = round(used / (1024**3), 1)
            info["disk_free_gb"] = round(free / (1024**3), 1)
            info["disk_percent"] = round(used / max(total, 1) * 100)
        except Exception:
            pass

        # Power / electricity info
        try:
            power = self._get_power_info()
            info.update(power)
        except Exception:
            pass

        # Current booth settings (from TOML config)
        try:
            info["settings"] = self._get_booth_settings()
        except Exception:
            info["settings"] = {}

        return info

    def _get_power_info(self) -> dict:
        """Read power/electricity data from the Raspberry Pi.

        On Pi 5: uses `vcgencmd pmic_read_adc` to read voltage and current
        from the PMIC rails, then sums up total board power consumption.

        On all Pis: uses `vcgencmd get_throttled` to report undervoltage
        and throttling state.

        Returns dict with keys: power_voltage, power_current_a, power_watts,
        power_throttled.
        """
        result: dict = {}

        # --- Throttle status (works on all Pis) ---
        try:
            out = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True, text=True, timeout=3,
            )
            if out.returncode == 0:
                # Output: throttled=0x0
                val = out.stdout.strip().split("=")[-1]
                flags = int(val, 16) if val.startswith("0x") else int(val)
                # Decode throttle flags
                issues = []
                if flags & 0x1:
                    issues.append("undervoltage")
                if flags & 0x2:
                    issues.append("freq_capped")
                if flags & 0x4:
                    issues.append("throttled")
                if flags & 0x8:
                    issues.append("temp_limit")
                # Historical flags (bits 16-19)
                if flags & 0x10000:
                    issues.append("was_undervoltage")
                if flags & 0x20000:
                    issues.append("was_freq_capped")
                if flags & 0x40000:
                    issues.append("was_throttled")
                if flags & 0x80000:
                    issues.append("was_temp_limit")
                result["power_throttled"] = ",".join(issues) if issues else "ok"
        except Exception:
            pass

        # --- PMIC ADC readings (Raspberry Pi 5 only) ---
        try:
            out = subprocess.run(
                ["vcgencmd", "pmic_read_adc"],
                capture_output=True, text=True, timeout=3,
            )
            if out.returncode == 0 and out.stdout.strip():
                total_power_mw = 0.0
                ext5v_voltage = None

                for line in out.stdout.strip().splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    # Parse voltage lines: "EXT5V_V volt(24)=5.08262000V"
                    v_match = re.match(
                        r"(\S+)\s+volt\(\d+\)\s*=\s*([\d.]+)V", line
                    )
                    if v_match:
                        rail_name = v_match.group(1)
                        volts = float(v_match.group(2))
                        if rail_name == "EXT5V_V":
                            ext5v_voltage = round(volts, 2)
                        continue

                    # Parse current lines: "VDD_CORE_A current(7)=0.88407000A"
                    c_match = re.match(
                        r"(\S+)\s+current\(\d+\)\s*=\s*([\d.]+)A", line
                    )
                    if c_match:
                        rail_name = c_match.group(1)
                        amps = float(c_match.group(2))
                        # Estimate power per rail (V × I); using 5V as
                        # approximate input voltage for total board power
                        # The actual rail voltage varies but 5V input is
                        # what matters for total consumption
                        total_power_mw += amps * 5.0 * 1000  # mW
                        continue

                if ext5v_voltage is not None:
                    result["power_voltage"] = ext5v_voltage
                    # Recalculate using actual input voltage
                    total_current_a = total_power_mw / 1000 / 5.0  # back to amps
                    result["power_current_a"] = round(total_current_a, 2)
                    result["power_watts"] = round(
                        ext5v_voltage * total_current_a, 1
                    )
        except FileNotFoundError:
            pass  # vcgencmd not available (not a Pi)
        except Exception:
            pass

        return result

    def _get_booth_settings(self) -> dict:
        """Read current booth settings for remote display."""
        try:
            import tomllib
            toml_path = Path("/opt/photobooth/booth.toml")
            if not toml_path.exists():
                toml_path = Path("booth.toml")
            if toml_path.exists():
                with open(toml_path, "rb") as f:
                    cfg = tomllib.load(f)
                return {
                    "event_name": cfg.get("app", {}).get("event_name", ""),
                    "language": cfg.get("app", {}).get("language", "nl"),
                    "theme": cfg.get("app", {}).get("theme", "classic"),
                    "camera_backend": cfg.get("camera", {}).get("backend", "webcam"),
                    "camera_iso": cfg.get("camera", {}).get("iso", "auto"),
                    "camera_aperture": cfg.get("camera", {}).get("aperture", ""),
                    "camera_shutter": cfg.get("camera", {}).get("shutter_speed", "auto"),
                    "resolution": f"{cfg.get('app', {}).get('width', '?')}x{cfg.get('app', {}).get('height', '?')}",
                    "first_countdown": cfg.get("countdown", {}).get("first_countdown", 5),
                    "between_shots": cfg.get("countdown", {}).get("between_shots", 3),
                    "led_enabled": cfg.get("led", {}).get("enabled", False),
                    "led_brightness": cfg.get("led", {}).get("brightness", 0),
                }
        except Exception:
            pass
        return {}

    def _get_cpu_percent(self) -> int:
        """Get CPU usage percentage."""
        try:
            load_1min = os.getloadavg()[0]
            cpu_count = os.cpu_count() or 1
            return min(int((load_1min / cpu_count) * 100), 100)
        except (OSError, AttributeError):
            return 0

    def _is_camera_connected(self) -> bool:
        """Check if a camera device is available."""
        if platform.system() == "Linux":
            return Path("/dev/video0").exists()
        return True

    async def send_message(self, msg: dict):
        """Send a message to the server (if connected)."""
        if self._ws:
            try:
                await self._ws.send(json.dumps(msg))
            except Exception as e:
                logger.warning("Send failed: %s", e)

    def send_log(self, level: str, message: str, logger_name: str) -> None:
        """Queue a log message for sending to the server (thread-safe)."""
        if not self._ws or not self._loop or not self._running:
            return
        msg = {
            "type": "log",
            "level": level,
            "message": message,
            "logger": logger_name,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self.send_message(msg),
            )
        except RuntimeError:
            pass  # Loop closed


class _WSLogHandler(logging.Handler):
    """Logging handler that forwards records to the admin server via WS.

    Filters out agent-internal logs to avoid infinite recursion.
    """

    def __init__(self, agent: BoothAgent):
        super().__init__()
        self._agent = agent
        # Loggers to ignore (prevents log loops)
        self._ignore = {"websockets", "asyncio", __name__}

    def emit(self, record: logging.LogRecord) -> None:
        # Skip internal loggers to avoid loops
        if record.name in self._ignore or record.name.startswith("websockets"):
            return
        try:
            msg = self.format(record) if self.formatter else record.getMessage()
            self._agent.send_log(record.levelname, msg, record.name)
        except Exception:
            pass  # Never crash the app for logging
