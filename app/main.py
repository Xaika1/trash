import asyncio
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db

MAX_BLOCKS = 2000
MAX_TEXT = 1000
MAX_ID = 2**62
MAX_COORD = 1_000_000

clients = set()


@asynccontextmanager
async def lifespan(app):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    await db.count_blocks()
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


async def send_to(client, line):
    try:
        await asyncio.wait_for(client.send_text(line), 5)
    except Exception:
        clients.discard(client)


async def send_all(line, skip=None):
    targets = [client for client in clients if client is not skip]
    await asyncio.gather(*(send_to(client, line) for client in targets))


async def create_block(line):
    _, block_type, x, y, width, height, text = line.split(";", 6)
    if len(text) > MAX_TEXT or await db.count_blocks() >= MAX_BLOCKS:
        return
    coordinates = to_coordinates(x, y, width, height)
    block = await db.add_block(to_int(block_type, 1, 4), coordinates, text)
    await send_all(block_line(block))


async def drag_block(line, sender):
    _, block_id, x, y = line.split(";")
    x = to_int(x, -MAX_COORD, MAX_COORD)
    y = to_int(y, -MAX_COORD, MAX_COORD)
    await send_all(f"M;{to_id(block_id)};{x};{y}", skip=sender)


async def place_block(line):
    _, block_id, x, y, width, height = line.split(";")
    block = await db.move_block(to_id(block_id), to_coordinates(x, y, width, height))
    if block:
        await send_all(block_line(block))


async def rename_block(line):
    _, block_id, text = line.split(";", 2)
    if len(text) > MAX_TEXT:
        return
    block = await db.rename_block(to_id(block_id), text)
    if block:
        await send_all(block_line(block))


async def remove_block(line):
    _, block_id = line.split(";")
    block_id = to_id(block_id)
    await db.delete_block(block_id)
    await send_all(f"X;{block_id}")


async def create_edge(line):
    _, from_block, from_side, to_block, to_side_value = line.split(";")
    from_block = to_id(from_block)
    to_block = to_id(to_block)
    if from_block == to_block:
        return
    edge = await db.add_edge(from_block, to_side(from_side), to_block, to_side(to_side_value))
    if edge:
        await send_all(edge_line(edge))


async def remove_edge(line):
    _, edge_id = line.split(";")
    edge_id = to_id(edge_id)
    await db.delete_edge(edge_id)
    await send_all(f"D;{edge_id}")


async def handle(line, sender):
    command = line[:1]
    if command == "A":
        await create_block(line)
    elif command == "M":
        await drag_block(line, sender)
    elif command == "F":
        await place_block(line)
    elif command == "T":
        await rename_block(line)
    elif command == "X":
        await remove_block(line)
    elif command == "E":
        await create_edge(line)
    elif command == "D":
        await remove_edge(line)


@app.websocket("/ws")
async def websocket(socket: WebSocket):
    await socket.accept()

    for block in await db.get_blocks():
        await socket.send_text(block_line(block))
    for edge in await db.get_edges():
        await socket.send_text(edge_line(edge))

    clients.add(socket)
    try:
        while True:
            line = await socket.receive_text()
            try:
                await handle(line, socket)
            except (ValueError, asyncpg.ForeignKeyViolationError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(socket)
