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
from pathlib import Path

logger = logging.getLogger(__name__)


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
        logger.info("Connecting to %s ...", ws_url)

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
