"""Shared WebSocket protocol types between booth and server."""
from enum import StrEnum


class BoothMessage(StrEnum):
    """Messages from Booth → Server."""
    REGISTER = "register"
    HEARTBEAT = "heartbeat"
    FRAME = "frame"
    PHOTO_READY = "photo_ready"
    LOG = "log"


class ServerCommand(StrEnum):
    """Commands from Server → Booth."""
    START_PREVIEW = "start_preview"
    STOP_PREVIEW = "stop_preview"
    UPDATE_SETTINGS = "update_settings"
    RESTART = "restart"
    UPLOAD_PHOTO = "upload_photo"
    ACK = "ack"


class BoothStatus(StrEnum):
    """Booth connection status."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class Role(StrEnum):
    """User roles for authorization."""
    ADMIN = "admin"
    USER = "user"
    BOOTH = "booth"
