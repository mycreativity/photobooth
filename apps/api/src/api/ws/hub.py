"""WebSocket connection hub — manages booth and admin connections."""
import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionHub:
    """Central hub for all WebSocket connections.

    Tracks connected booths and admin viewers so we can:
    - Relay camera frames from booth → admin viewer
    - Send commands from admin → booth
    - Detect booth disconnect (heartbeat timeout)
    """

    def __init__(self):
        # booth_id → WebSocket
        self._booths: dict[str, WebSocket] = {}
        # booth_id → set of admin WebSockets watching this booth
        self._admin_viewers: dict[str, set[WebSocket]] = {}
        # booth_id → last heartbeat time
        self._last_heartbeat: dict[str, datetime] = {}
        # booth_id → full heartbeat info (system metrics + settings)
        self._booth_info: dict[str, dict] = {}
        # booth_id → log ring buffer (last N log lines)
        self._booth_logs: dict[str, deque] = {}

    @property
    def connected_booths(self) -> list[str]:
        """List of currently connected booth IDs."""
        return list(self._booths.keys())

    def register_booth(self, booth_id: str, ws: WebSocket) -> None:
        """Register a booth WebSocket connection."""
        self._booths[booth_id] = ws
        self._last_heartbeat[booth_id] = datetime.now(timezone.utc)
        logger.info("Booth connected: %s", booth_id)

    def unregister_booth(self, booth_id: str) -> None:
        """Remove a booth connection."""
        self._booths.pop(booth_id, None)
        self._last_heartbeat.pop(booth_id, None)
        logger.info("Booth disconnected: %s", booth_id)

    def register_admin_viewer(self, booth_id: str, ws: WebSocket) -> None:
        """Admin starts watching a booth's camera feed."""
        if booth_id not in self._admin_viewers:
            self._admin_viewers[booth_id] = set()
        self._admin_viewers[booth_id].add(ws)
        logger.info("Admin viewer added for booth %s", booth_id)

    def unregister_admin_viewer(self, booth_id: str, ws: WebSocket) -> None:
        """Admin stops watching."""
        viewers = self._admin_viewers.get(booth_id)
        if viewers:
            viewers.discard(ws)
            if not viewers:
                del self._admin_viewers[booth_id]

    def update_heartbeat(self, booth_id: str, info: dict | None = None) -> None:
        """Update last heartbeat time and store system info."""
        self._last_heartbeat[booth_id] = datetime.now(timezone.utc)
        if info:
            self._booth_info[booth_id] = info

    def get_booth_info(self, booth_id: str) -> dict:
        """Get the latest system info for a booth."""
        return self._booth_info.get(booth_id, {})

    def append_log(self, booth_id: str, log_entry: dict) -> None:
        """Store a log line in the ring buffer."""
        if booth_id not in self._booth_logs:
            self._booth_logs[booth_id] = deque(maxlen=200)
        self._booth_logs[booth_id].append(log_entry)

    def get_logs(self, booth_id: str, limit: int = 100) -> list[dict]:
        """Get recent log lines for a booth."""
        buf = self._booth_logs.get(booth_id, deque())
        return list(buf)[-limit:]

    async def relay_log_to_admins(self, booth_id: str, log_entry: dict) -> None:
        """Send a log entry to all admin viewers watching this booth."""
        viewers = self._admin_viewers.get(booth_id, set())
        if not viewers:
            return

        dead = set()
        msg = {"type": "log", "booth_id": booth_id, **log_entry}

        for ws in viewers:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.add(ws)

        for ws in dead:
            viewers.discard(ws)

    async def send_to_booth(self, booth_id: str, message: dict) -> bool:
        """Send a JSON message to a specific booth."""
        ws = self._booths.get(booth_id)
        if not ws:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as e:
            logger.warning("Failed to send to booth %s: %s", booth_id, e)
            self.unregister_booth(booth_id)
            return False

    async def relay_frame_to_admins(self, booth_id: str, frame_data: str) -> None:
        """Relay a camera frame (base64) to all admin viewers."""
        viewers = self._admin_viewers.get(booth_id, set())
        if not viewers:
            return

        dead = set()
        msg = {"type": "frame", "booth_id": booth_id, "data": frame_data}

        for ws in viewers:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.add(ws)

        for ws in dead:
            viewers.discard(ws)

    def is_booth_connected(self, booth_id: str) -> bool:
        return booth_id in self._booths

    def get_viewer_count(self, booth_id: str) -> int:
        return len(self._admin_viewers.get(booth_id, set()))

    def get_stale_booths(self, max_age_seconds: int = 30) -> list[str]:
        """Return booth IDs that haven't sent a heartbeat within max_age_seconds.

        Also unregisters them from the hub so they no longer receive commands.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        stale = []
        for booth_id, last_hb in list(self._last_heartbeat.items()):
            if last_hb < cutoff:
                stale.append(booth_id)
                self.unregister_booth(booth_id)
        return stale


# Global singleton
hub = ConnectionHub()
