"""Booth Agent — WebSocket client connecting to the admin server.

Runs as a background thread alongside the Kivy main loop.
Handles:
- Registration with the server
- Periodic heartbeats (CPU %, camera status, uptime)
- Receiving commands (start/stop preview, update settings, restart)
- Reconnection with exponential backoff
"""
import asyncio
import json
import logging
import os
import platform
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

    def __init__(self, config: dict):
        self._config = config
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

        ws_url = f"{self._url}/ws/booth/{self._booth_id}"
        api_key = self._config.get("api_key", "")
        if api_key:
            ws_url += f"?api_key={api_key}"
        logger.info("Connecting to %s ...", ws_url.split("?")[0])  # Don't log the key

        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
            self._ws = ws
            logger.info("Connected to server")

            # Send registration
            await ws.send(json.dumps({
                "type": "register",
                "booth_id": self._booth_id,
                "name": self._booth_name,
                "version": "0.1.0",
            }))

            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

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
                    elif msg_type == "update_settings":
                        self._handle_update_settings(msg.get("settings", {}))
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

        # Current booth settings (from TOML config)
        try:
            info["settings"] = self._get_booth_settings()
        except Exception:
            info["settings"] = {}

        return info

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
