"""WebSocket endpoint for admin live camera viewing."""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.auth.oauth2 import decode_token
from server.ws.hub import hub

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/admin/{booth_id}")
async def admin_websocket(websocket: WebSocket, booth_id: str):
    """Admin WebSocket for live camera viewing of a specific booth.

    The admin frontend connects here and receives relayed camera
    frames from the booth. Can also send commands (start/stop preview).

    Auth: token passed as query parameter ?token=<jwt>
    """
    # Authenticate via query parameter
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_token(token)
    if not payload or payload.get("role") != "admin":
        await websocket.close(code=4003, reason="Unauthorized")
        return

    await websocket.accept()
    hub.register_admin_viewer(booth_id, websocket)

    # If no admin was watching before, tell the booth to start preview
    if hub.get_viewer_count(booth_id) == 1:
        await hub.send_to_booth(booth_id, {"type": "start_preview"})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            # Forward commands to booth
            if msg_type in ("start_preview", "stop_preview", "restart", "capture_photo"):
                await hub.send_to_booth(booth_id, msg)
                logger.info("Admin command → booth %s: %s", booth_id, msg_type)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Admin WS error for booth %s: %s", booth_id, e)
    finally:
        hub.unregister_admin_viewer(booth_id, websocket)
        # If no more admins watching, tell booth to stop preview
        if hub.get_viewer_count(booth_id) == 0:
            await hub.send_to_booth(booth_id, {"type": "stop_preview"})
