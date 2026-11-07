from contextlib import asynccontextmanager

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import auth, db, editor
from app.editor import CLOSED, block_line, edge_line, role_of


class Account(BaseModel):
    login: str = Field(max_length=64)
    password: str = Field(max_length=200)
    password_confirm: str = Field(default="", max_length=200)


class CanvasData(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    access: int | None = Field(default=None, ge=0, le=2)


@asynccontextmanager
async def lifespan(app):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def json_only(request: Request, call_next):
    if request.method in ("POST", "PATCH", "DELETE") and request.url.path.startswith("/api/"):
        if request.method != "DELETE" and not request.headers.get("content-type", "").startswith("application/json"):
            return Response("Нужен JSON", status_code=415)
    return await call_next(request)


@app.get("/")
async def canvases_page():
    return FileResponse("static/canvases.html")


@app.get("/login")
async def login_page():
    return FileResponse("static/login.html")


@app.get("/canvas/{canvas_id}")
async def canvas_page(canvas_id: int):
    return FileResponse("static/canvas.html")


@app.get("/share/{code}")
async def share_page(code: str):
    return FileResponse("static/canvas.html")


@app.get("/health")
async def health():
    await db.ping()
    return {"status": "ok"}


@app.post("/api/register")
async def register(data: Account, request: Request, response: Response):
    if auth.too_many_attempts(request.client.host):
        raise HTTPException(429, "Слишком много попыток, подождите минуту")
    auth.check_login(data.login)
    auth.check_password(data.password, data.password_confirm)
    user = await db.add_user(data.login, await auth.hash_password(data.password))
    if not user:
        raise HTTPException(409, "Такой логин уже занят")
    await auth.start_session(request, response, user["id"])
    return {"login": user["login"]}


@app.post("/api/login")
async def login(data: Account, request: Request, response: Response):
    if auth.too_many_attempts(request.client.host):
        raise HTTPException(429, "Слишком много попыток, подождите минуту")
    user = await db.get_user_by_login(data.login)
    if not user or not await auth.verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Неверный логин или пароль")
    await auth.start_session(request, response, user["id"])
    return {"login": user["login"]}


@app.post("/api/logout")
async def logout(request: Request, response: Response):
    await auth.end_session(request, response)
    return {"status": "ok"}


@app.get("/api/me")
async def me(user=Depends(auth.current_user)):
    return {"login": user["login"]}


def canvas_info(canvas):
    return {
        "id": canvas["id"],
        "title": canvas["title"],
        "access": canvas["access"],
        "link": f"/share/{canvas['share_code']}",
    }


async def own_canvas(canvas_id, user):
    canvas = await db.get_canvas(canvas_id)
    if not canvas or canvas["owner_id"] != user["id"]:
        raise HTTPException(404, "Холст не найден")
    return canvas


@app.get("/api/canvases")
async def list_canvases(user=Depends(auth.current_user)):
    return [canvas_info(canvas) for canvas in await db.get_canvases(user["id"])]


@app.post("/api/canvases")
async def create_canvas(data: CanvasData, user=Depends(auth.current_user)):
    canvas = await db.add_canvas(user["id"], data.title or "Новый холст")
    return canvas_info(canvas)


@app.patch("/api/canvases/{canvas_id}")
async def change_canvas(canvas_id: int, data: CanvasData, user=Depends(auth.current_user)):
    canvas = await own_canvas(canvas_id, user)
    if data.title is not None:
        canvas = await db.rename_canvas(canvas_id, data.title)
        await editor.send_room(canvas_id, f"I;title;{canvas['title']}")
    if data.access is not None:
        canvas = await db.set_access(canvas_id, data.access)
        await editor.apply_access(canvas_id, data.access)
    return canvas_info(canvas)


@app.delete("/api/canvases/{canvas_id}")
async def remove_canvas(canvas_id: int, user=Depends(auth.current_user)):
    await own_canvas(canvas_id, user)
    await db.delete_canvas(canvas_id)
    await editor.close_room(canvas_id, "Холст удалён")
    return {"status": "ok"}


async def open_canvas(user, canvas_id, code):
    if code:
        canvas = await db.get_canvas_by_code(code)
    elif canvas_id:
        canvas = await db.get_canvas(int(canvas_id))
    else:
        canvas = None
    if not canvas:
        return None, None
    if canvas["owner_id"] == user["id"]:
        return canvas, True
    if code and canvas["access"] != CLOSED:
        return canvas, False
    return None, None


@app.websocket("/ws")
async def websocket(socket: WebSocket):
    await socket.accept()
    origin = socket.headers.get("origin", "")
    host = socket.headers.get("host", "")
    if origin.split("://")[-1] != host:
        await socket.close(4403)
        return

    user = await auth.find_user(socket.cookies.get(auth.COOKIE))
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
    await socket.send_text(f"I;title;{canvas['title']}")
    await socket.send_text(f"I;role;{member['role']}")
    await socket.send_text(f"I;id;{canvas_id}")
    if owner:
        await socket.send_text(f"I;access;{canvas['access']}")
        await socket.send_text(f"I;link;/share/{canvas['share_code']}")

    for block in await db.get_blocks(canvas_id):
        await socket.send_text(block_line(block))
    for edge in await db.get_edges(canvas_id):
        await socket.send_text(edge_line(edge))

    await editor.join(canvas_id, socket, member)
    try:
        while True:
            line = await socket.receive_text()
            if member["role"] == "view":
                continue
            try:
                await editor.handle(canvas_id, line, member, socket)
            except (ValueError, asyncpg.ForeignKeyViolationError, asyncpg.UniqueViolationError):
                pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await editor.leave(canvas_id, socket)
