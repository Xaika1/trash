from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/")
async def canvases_page():
    return FileResponse("static/canvases.html")


@router.get("/login")
async def login_page():
    return FileResponse("static/login.html")


@router.get("/canvas/{canvas_id}")
async def canvas_page(canvas_id: int):
    return FileResponse("static/canvas.html")


@router.get("/share/{code}")
async def share_page(code: str):
    return FileResponse("static/canvas.html")
