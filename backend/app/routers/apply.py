"""Auto-apply control + SSE stream routes."""
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..automation import engine
from ..deps import get_approved_user
from ..models import User
from ..security import decode_access_token

router = APIRouter(prefix="/api/apply", tags=["apply"])


@router.post("/start")
async def start_apply(user: User = Depends(get_approved_user)):
    started = engine.start(user.id)
    if not started:
        return {"message": "Already running", "running": True}
    return {"message": "Auto-apply started", "running": True}


@router.post("/stop")
async def stop_apply(user: User = Depends(get_approved_user)):
    stopped = await engine.stop(user.id)
    return {"message": "Stopped" if stopped else "Nothing running", "running": False}


@router.get("/status")
def apply_status(user: User = Depends(get_approved_user)):
    return {"running": engine.is_running(user.id)}


@router.get("/stream")
async def stream(request: Request, token: str = ""):
    """SSE stream of live apply events.

    EventSource cannot set Authorization headers, so the JWT is passed as a
    query parameter (``?token=...``).
    """
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return StreamingResponse(iter(["event: error\ndata: unauthorized\n\n"]),
                                 media_type="text/event-stream")
    user_id = int(payload["sub"])
    queue = engine.get_queue(user_id)

    async def event_gen():
        # Initial hello so the client knows the stream is open.
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    # Keep stream open; client may start again. Send a keepalive.
                    pass
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"  # SSE comment to keep connection alive

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
