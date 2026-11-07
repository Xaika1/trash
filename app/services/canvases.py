from fastapi import HTTPException

from app.database import canvases
from app.editor.roles import CLOSED


def canvas_info(canvas):
    return {
        "id": canvas["id"],
        "title": canvas["title"],
        "access": canvas["access"],
        "link": f"/share/{canvas['share_code']}",
    }


async def own_canvas(canvas_id, user):
    canvas = await canvases.get(canvas_id)
    if not canvas or canvas["owner_id"] != user["id"]:
        raise HTTPException(404, "Холст не найден")
    return canvas


async def open_canvas(user, canvas_id, code):
    if code:
        canvas = await canvases.get_by_code(code)
    elif canvas_id:
        canvas = await canvases.get(int(canvas_id))
    else:
        canvas = None
    if not canvas:
        return None, None
    if canvas["owner_id"] == user["id"]:
        return canvas, True
    if code and canvas["access"] != CLOSED:
        return canvas, False
    return None, None
