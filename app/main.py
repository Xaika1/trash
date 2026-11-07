import asyncio
from contextlib import asynccontextmanager

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import auth, db

MAX_BLOCKS = 2000
MAX_TEXT = 1000
MAX_ID = 2**62
MAX_COORD = 1_000_000

CLOSED = 0
VIEW = 1
EDIT = 2

rooms = {}


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
    await auth.start_session(response, user["id"])
    return {"login": user["login"]}


@app.post("/api/login")
async def login(data: Account, request: Request, response: Response):
    if auth.too_many_attempts(request.client.host):
        raise HTTPException(429, "Слишком много попыток, подождите минуту")
    user = await db.get_user_by_login(data.login)
    if not user or not await auth.verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Неверный логин или пароль")
    await auth.start_session(response, user["id"])
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
        await send_room(canvas_id, f"I;title;{canvas['title']}")
    if data.access is not None:
        canvas = await db.set_access(canvas_id, data.access)
        await apply_access(canvas_id, data.access)
    return canvas_info(canvas)


@app.delete("/api/canvases/{canvas_id}")
async def remove_canvas(canvas_id: int, user=Depends(auth.current_user)):
    await own_canvas(canvas_id, user)
    await db.delete_canvas(canvas_id)
    await close_room(canvas_id, "Холст удалён")
    return {"status": "ok"}


def to_int(value, low, high):
    number = int(value)
    if not low <= number <= high:
        raise ValueError
    return number


def to_id(value):
    return to_int(value, 1, MAX_ID)


def to_side(value):
    return to_int(value, 0, 3)


def to_coordinates(x, y, width, height):
    x = to_int(x, -MAX_COORD, MAX_COORD)
    y = to_int(y, -MAX_COORD, MAX_COORD)
    width = to_int(width, 20, 5000)
    height = to_int(height, 20, 5000)
    return f"{x};{y};{width};{height}"


def block_line(block):
    return f"N;{block['id']};{block['type']};{block['coordinates']};{block['text']}"


def edge_line(edge):
    sides = f"{edge['from_block']};{edge['from_side']};{edge['to_block']};{edge['to_side']}"
    return f"E;{edge['id']};{sides}"


def role_of(owner, access):
    if owner:
        return "owner"
    return "edit" if access == EDIT else "view"


async def send_to(canvas_id, socket, line):
    try:
        await asyncio.wait_for(socket.send_text(line), 5)
    except Exception:
        rooms.get(canvas_id, {}).pop(socket, None)


async def send_room(canvas_id, line, skip=None):
    members = rooms.get(canvas_id, {})
    targets = [socket for socket in members if socket is not skip]
    await asyncio.gather(*(send_to(canvas_id, socket, line) for socket in targets))


async def apply_access(canvas_id, access):
    for socket, member in list(rooms.get(canvas_id, {}).items()):
        if member["role"] == "owner":
            continue
        if access == CLOSED:
            await send_to(canvas_id, socket, "C;Владелец закрыл доступ")
            await socket.close(4403)
        else:
            member["role"] = role_of(False, access)
            await send_to(canvas_id, socket, f"I;role;{member['role']}")


async def close_room(canvas_id, reason):
    for socket in list(rooms.get(canvas_id, {})):
        await send_to(canvas_id, socket, f"C;{reason}")
        await socket.close(4404)
    rooms.pop(canvas_id, None)


async def create_block(canvas_id, line):
    _, block_type, x, y, width, height, text = line.split(";", 6)
    if len(text) > MAX_TEXT or await db.count_blocks(canvas_id) >= MAX_BLOCKS:
        return
    coordinates = to_coordinates(x, y, width, height)
    block = await db.add_block(canvas_id, to_int(block_type, 1, 4), coordinates, text)
    await send_room(canvas_id, block_line(block))


async def drag_block(canvas_id, line, sender):
    _, block_id, x, y = line.split(";")
    x = to_int(x, -MAX_COORD, MAX_COORD)
    y = to_int(y, -MAX_COORD, MAX_COORD)
    await send_room(canvas_id, f"M;{to_id(block_id)};{x};{y}", skip=sender)


async def place_block(canvas_id, line):
    _, block_id, x, y, width, height = line.split(";")
    block = await db.move_block(canvas_id, to_id(block_id), to_coordinates(x, y, width, height))
    if block:
        await send_room(canvas_id, block_line(block))


async def rename_block(canvas_id, line):
    _, block_id, text = line.split(";", 2)
    if len(text) > MAX_TEXT:
        return
    block = await db.rename_block(canvas_id, to_id(block_id), text)
    if block:
        await send_room(canvas_id, block_line(block))


async def remove_block(canvas_id, line):
    _, block_id = line.split(";")
    block_id = to_id(block_id)
    await db.delete_block(canvas_id, block_id)
    await send_room(canvas_id, f"X;{block_id}")


async def create_edge(canvas_id, line):
    _, from_block, from_side, to_block, to_side_value = line.split(";")
    from_block = to_id(from_block)
    to_block = to_id(to_block)
    if from_block == to_block:
        return
    edge = await db.add_edge(canvas_id, from_block, to_side(from_side), to_block, to_side(to_side_value))
    if edge:
        await send_room(canvas_id, edge_line(edge))


async def remove_edge(canvas_id, line):
    _, edge_id = line.split(";")
    edge_id = to_id(edge_id)
    await db.delete_edge(canvas_id, edge_id)
    await send_room(canvas_id, f"D;{edge_id}")


async def handle(canvas_id, line, sender):
    command = line[:1]
    if command == "A":
        await create_block(canvas_id, line)
    elif command == "M":
        await drag_block(canvas_id, line, sender)
    elif command == "F":
        await place_block(canvas_id, line)
    elif command == "T":
        await rename_block(canvas_id, line)
    elif command == "X":
        await remove_block(canvas_id, line)
    elif command == "E":
        await create_edge(canvas_id, line)
    elif command == "D":
        await remove_edge(canvas_id, line)


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
    member = {"role": role_of(owner, canvas["access"])}
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

    rooms.setdefault(canvas_id, {})[socket] = member
    try:
        while True:
            line = await socket.receive_text()
            if member["role"] == "view":
                continue
            try:
                await handle(canvas_id, line, socket)
            except (ValueError, asyncpg.ForeignKeyViolationError):
                pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        rooms.get(canvas_id, {}).pop(socket, None)
        if not rooms.get(canvas_id):
            rooms.pop(canvas_id, None)
