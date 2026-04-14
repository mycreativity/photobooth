"""WebSocket endpoint for booth devices."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from server.database import get_db
from server.models.db import Booth, hash_api_key
from server.ws.hub import hub

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/booth/{booth_id}")
async def booth_websocket(websocket: WebSocket, booth_id: str):
    """Persistent WebSocket connection for a photobooth device.

    Auth: booth must provide api_key as query parameter.
    If the booth has no api_key_hash set (legacy), connection is allowed with a warning.

    Protocol:
    - Booth sends: register, heartbeat, frame, photo_ready, log
    - Server sends: start_preview, stop_preview, update_settings, restart
    """
    # --- Authenticate ---
    api_key = websocket.query_params.get("api_key", "")

    booth = None
    async for db in get_db():
        result = await db.execute(
            select(Booth).where(Booth.booth_id == booth_id)
        )
        booth = result.scalar_one_or_none()

    # Must accept before we can close with a code
    await websocket.accept()

    if not booth:
        logger.warning("WS connect rejected: unknown booth_id=%s", booth_id)
        await websocket.close(code=4001, reason="Unknown booth")
        return

    # Validate API key (if booth has one set)
    if booth.api_key_hash:
        if not api_key or hash_api_key(api_key) != booth.api_key_hash:
            logger.warning("WS connect rejected: invalid API key for booth=%s", booth_id)
            await websocket.close(code=4001, reason="Invalid API key")
            return
    else:
        logger.warning("Booth %s has no API key set — allowing connection (legacy mode)", booth_id)

    hub.register_booth(booth_id, websocket)

    # Update booth status in DB
    async for db in get_db():
        result = await db.execute(
            select(Booth).where(Booth.booth_id == booth_id)
        )
        booth = result.scalar_one_or_none()
        if booth:
            booth.status = "online"
            booth.last_seen = datetime.now(timezone.utc)
            await db.commit()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from booth %s", booth_id)
                continue

            msg_type = msg.get("type", "")

            if msg_type == "heartbeat":
                hub.update_heartbeat(booth_id, msg)
                # Update booth status in DB
                async for db in get_db():
                    result = await db.execute(
                        select(Booth).where(Booth.booth_id == booth_id)
                    )
                    booth = result.scalar_one_or_none()
                    if booth:
                        booth.last_seen = datetime.now(timezone.utc)
                        booth.cpu_percent = msg.get("cpu")
                        booth.camera_connected = msg.get("cam_connected", False)
                        booth.uptime_seconds = msg.get("uptime")
                        booth.status = "online"
                        await db.commit()

            elif msg_type == "register":
                logger.info(
                    "Booth registered: %s (name=%s, version=%s)",
                    booth_id, msg.get("name"), msg.get("version"),
                )
                async for db in get_db():
                    result = await db.execute(
                        select(Booth).where(Booth.booth_id == booth_id)
                    )
                    booth = result.scalar_one_or_none()
                    if booth:
                        booth.name = msg.get("name", booth.name)
                        booth.version = msg.get("version", booth.version)
                        booth.status = "online"
                        booth.last_seen = datetime.now(timezone.utc)
                        await db.commit()

                await websocket.send_json({"type": "ack", "status": "registered"})

            elif msg_type == "frame":
                # Relay camera frame to any admin viewers
                await hub.relay_frame_to_admins(booth_id, msg.get("data", ""))

            elif msg_type == "photo_ready":
                logger.info(
                    "Photo ready: booth=%s session=%s seq=%s",
                    booth_id, msg.get("session_id"), msg.get("seq"),
                )

            elif msg_type == "log":
                log_entry = {
                    "level": msg.get("level", "INFO"),
                    "message": msg.get("message", ""),
                    "logger": msg.get("logger", ""),
                    "ts": msg.get("ts", ""),
                }
                hub.append_log(booth_id, log_entry)
                await hub.relay_log_to_admins(booth_id, log_entry)

            else:
                logger.debug("Unknown message type from %s: %s", booth_id, msg_type)

    except WebSocketDisconnect:
        logger.info("Booth %s disconnected", booth_id)
    except Exception as e:
        logger.error("Booth %s WS error: %s", booth_id, e)
    finally:
        hub.unregister_booth(booth_id)
        # Mark offline in DB
        async for db in get_db():
            result = await db.execute(
                select(Booth).where(Booth.booth_id == booth_id)
            )
            booth = result.scalar_one_or_none()
            if booth:
                booth.status = "offline"
                await db.commit()
