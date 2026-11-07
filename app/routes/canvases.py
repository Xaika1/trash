from fastapi import APIRouter, Depends

from app import config
from app.database import canvases
from app.editor import rooms
from app.schemas import CanvasData
from app.services.canvases import canvas_info, own_canvas
from app.services.sessions import current_user

router = APIRouter(prefix="/api/canvases")


@router.get("")
async def list_canvases(user=Depends(current_user)):
    return [canvas_info(canvas) for canvas in await canvases.get_by_owner(user["id"])]


@router.post("")
async def create_canvas(data: CanvasData, user=Depends(current_user)):
    canvas = await canvases.add(user["id"], data.title or config.CANVAS_DEFAULT_TITLE)
    return canvas_info(canvas)


@router.patch("/{canvas_id}")
async def change_canvas(canvas_id: int, data: CanvasData, user=Depends(current_user)):
    canvas = await own_canvas(canvas_id, user)
    if data.title is not None:
        canvas = await canvases.rename(canvas_id, data.title)
        await rooms.send_room(canvas_id, f"I;title;{canvas['title']}")
    if data.access is not None:
        canvas = await canvases.set_access(canvas_id, data.access)
        await rooms.apply_access(canvas_id, data.access)
    return canvas_info(canvas)


@router.delete("/{canvas_id}")
async def remove_canvas(canvas_id: int, user=Depends(current_user)):
    await own_canvas(canvas_id, user)
    await canvases.delete(canvas_id)
    await rooms.close_room(canvas_id, "Холст удалён")
    return {"status": "ok"}
