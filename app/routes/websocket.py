import asyncpg
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import config
from app.editor import rooms
from app.editor.commands import handle
from app.editor.roles import role_of
from app.editor.snapshot import send_snapshot
from app.services.canvases import open_canvas
from app.services.sessions import find_user

router = APIRouter()


def same_origin(socket):
    origin = socket.headers.get("origin", "")
    host = socket.headers.get("host", "")
    return origin.split("://")[-1] == host


@router.websocket("/ws")
async def websocket(socket: WebSocket):
    await socket.accept()
    if not same_origin(socket):
        await socket.close(4403)
        return

    user = await find_user(socket.cookies.get(config.SESSION_COOKIE))
    if not user:
        await socket.close(4401)
        return

    canvas_id = socket.query_params.get("canvas", "")
    code = socket.query_params.get("code", "")
    canvas, owner = await open_canvas(user, canvas_id if canvas_id.isdigit() else None, code)
    if not canvas:
        await socket.close(4404)
        return

    canvas_id = canvas["id"]
    member = {"role": role_of(owner, canvas["access"]), "user_id": user["id"], "login": user["login"]}
    await send_snapshot(socket, canvas, member, owner)

    await rooms.join(canvas_id, socket, member)
    try:
        while True:
            line = await socket.receive_text()
            if member["role"] == "view":
                continue
            try:
                await handle(canvas_id, line, member, socket)
            except (ValueError, asyncpg.ForeignKeyViolationError, asyncpg.UniqueViolationError):
                pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await rooms.leave(canvas_id, socket)
