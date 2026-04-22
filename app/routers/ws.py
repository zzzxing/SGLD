from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.db import SessionLocal
from app.core.websocket_manager import ws_manager
from app.services.classroom_service import touch_online

router = APIRouter()


@router.websocket("/ws/classroom/{session_id}")
async def classroom_ws(websocket: WebSocket, session_id: int, role: str = "student", user_id: int = 0):
    channel = f"student_session_{session_id}" if role == "student" else f"teacher_session_{session_id}"
    fallback_channel = "students_global" if role == "student" else channel
    await ws_manager.connect(channel, websocket, accept=True)
    if fallback_channel != channel:
        await ws_manager.connect(fallback_channel, websocket, accept=False)

    db = SessionLocal()
    try:
        if role == "student" and user_id:
            touch_online(db, session_id=session_id, student_id=user_id, is_online=True)
            await ws_manager.broadcast(
                f"teacher_session_{session_id}",
                {"type": "online_update", "student_id": user_id, "is_online": True},
            )

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if role == "student" and user_id:
            touch_online(db, session_id=session_id, student_id=user_id, is_online=False)
    finally:
        await ws_manager.disconnect(channel, websocket)
        if fallback_channel != channel:
            await ws_manager.disconnect(fallback_channel, websocket)
        if role == "student" and user_id:
            await ws_manager.broadcast(
                f"teacher_session_{session_id}",
                {"type": "online_update", "student_id": user_id, "is_online": False},
            )
        db.close()
