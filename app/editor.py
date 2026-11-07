import asyncio

from app import db

MAX_BLOCKS = 2000
MAX_TEXT = 1000
MAX_LABEL = 200
MAX_ID = 2**62
MAX_COORD = 1_000_000
UNDO_LIMIT = 10

CLOSED = 0
VIEW = 1
EDIT = 2

ROLE_ORDER = {"owner": 0, "edit": 1, "view": 2}
CONFLICT = "Нельзя откатить: это уже изменил кто-то другой"

rooms = {}
history = {}


class Refused(Exception):
    pass


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
    return f"E;{edge['id']};{sides};{edge['label']}"


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


async def send_people(canvas_id):
    people = {}
    for member in rooms.get(canvas_id, {}).values():
        old_role = people.get(member["login"])
        if old_role is None or ROLE_ORDER[member["role"]] < ROLE_ORDER[old_role]:
            people[member["login"]] = member["role"]
    names = sorted(people.items(), key=lambda item: (ROLE_ORDER[item[1]], item[0]))
    await send_room(canvas_id, "P;" + ",".join(f"{login}:{role}" for login, role in names))


async def join(canvas_id, socket, member):
    rooms.setdefault(canvas_id, {})[socket] = member
    await send_people(canvas_id)


async def leave(canvas_id, socket):
    members = rooms.get(canvas_id, {})
    members.pop(socket, None)
    if members:
        await send_people(canvas_id)
    else:
        rooms.pop(canvas_id, None)


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
    await send_people(canvas_id)


async def close_room(canvas_id, reason):
    for socket in list(rooms.get(canvas_id, {})):
        await send_to(canvas_id, socket, f"C;{reason}")
        await socket.close(4404)
    rooms.pop(canvas_id, None)
    for key in [key for key in history if key[0] == canvas_id]:
        del history[key]


def remember(canvas_id, member, step):
    steps = history.setdefault((canvas_id, member["user_id"]), [])
    steps.append(step)
    del steps[:-UNDO_LIMIT]


async def create_block(canvas_id, line, member):
    _, block_type, x, y, width, height, text = line.split(";", 6)
    if len(text) > MAX_TEXT or await db.count_blocks(canvas_id) >= MAX_BLOCKS:
        return
    coordinates = to_coordinates(x, y, width, height)
    block = await db.add_block(canvas_id, to_int(block_type, 1, 4), coordinates, text)
    remember(canvas_id, member, {"kind": "block_added", "id": block["id"], "after": block_line(block)})
    await send_room(canvas_id, block_line(block))


async def drag_block(canvas_id, line, sender):
    _, block_id, x, y = line.split(";")
    x = to_int(x, -MAX_COORD, MAX_COORD)
    y = to_int(y, -MAX_COORD, MAX_COORD)
    await send_room(canvas_id, f"M;{to_id(block_id)};{x};{y}", skip=sender)


async def change_block(canvas_id, block_id, member, block_type=None, coordinates=None, text=None):
    old = await db.get_block(canvas_id, block_id)
    if not old:
        return
    new = await db.update_block(
        canvas_id,
        block_id,
        old["type"] if block_type is None else block_type,
        old["coordinates"] if coordinates is None else coordinates,
        old["text"] if text is None else text,
    )
    if block_line(new) != block_line(old):
        remember(canvas_id, member, {"kind": "block_changed", "before": dict(old), "after": block_line(new)})
    await send_room(canvas_id, block_line(new))


async def place_block(canvas_id, line, member):
    _, block_id, x, y, width, height = line.split(";")
    await change_block(canvas_id, to_id(block_id), member, coordinates=to_coordinates(x, y, width, height))


async def rename_block(canvas_id, line, member):
    _, block_id, text = line.split(";", 2)
    if len(text) <= MAX_TEXT:
        await change_block(canvas_id, to_id(block_id), member, text=text)


async def retype_block(canvas_id, line, member):
    _, block_id, block_type = line.split(";")
    await change_block(canvas_id, to_id(block_id), member, block_type=to_int(block_type, 1, 4))


async def remove_block(canvas_id, line, member):
    _, block_id = line.split(";")
    block = await db.get_block(canvas_id, to_id(block_id))
    if not block:
        return
    edges = await db.get_block_edges(canvas_id, block["id"])
    await db.delete_block(canvas_id, block["id"])
    remember(canvas_id, member, {"kind": "block_deleted", "block": dict(block), "edges": [dict(edge) for edge in edges]})
    await send_room(canvas_id, f"X;{block['id']}")


async def create_edge(canvas_id, line, member):
    _, from_block, from_side, to_block, to_side_value = line.split(";")
    from_block = to_id(from_block)
    to_block = to_id(to_block)
    if from_block == to_block:
        return
    edge = await db.add_edge(canvas_id, from_block, to_side(from_side), to_block, to_side(to_side_value))
    if edge:
        remember(canvas_id, member, {"kind": "edge_added", "id": edge["id"], "after": edge_line(edge)})
        await send_room(canvas_id, edge_line(edge))


async def label_edge(canvas_id, line, member):
    _, edge_id, label = line.split(";", 2)
    old = await db.get_edge(canvas_id, to_id(edge_id))
    if not old or len(label) > MAX_LABEL:
        return
    new = await db.set_label(canvas_id, old["id"], label)
    if new["label"] != old["label"]:
        remember(canvas_id, member, {"kind": "edge_changed", "before": old["label"], "id": old["id"], "after": edge_line(new)})
    await send_room(canvas_id, edge_line(new))


async def remove_edge(canvas_id, line, member):
    _, edge_id = line.split(";")
    edge = await db.get_edge(canvas_id, to_id(edge_id))
    if not edge:
        return
    await db.delete_edge(canvas_id, edge["id"])
    remember(canvas_id, member, {"kind": "edge_deleted", "edge": dict(edge)})
    await send_room(canvas_id, f"D;{edge['id']}")


def to_ids(text):
    if not text:
        return []
    ids = [to_id(value) for value in text.split(",")]
    if len(ids) > MAX_BLOCKS * 2:
        raise ValueError
    return ids


async def remove_many(canvas_id, line, member):
    _, block_text, edge_text = line.split(";")
    removed_blocks = []
    removed_edges = {}

    for edge_id in to_ids(edge_text):
        edge = await db.get_edge(canvas_id, edge_id)
        if edge:
            removed_edges[edge["id"]] = dict(edge)
            await db.delete_edge(canvas_id, edge["id"])
            await send_room(canvas_id, f"D;{edge['id']}")

    for block_id in to_ids(block_text):
        block = await db.get_block(canvas_id, block_id)
        if not block:
            continue
        for edge in await db.get_block_edges(canvas_id, block_id):
            removed_edges[edge["id"]] = dict(edge)
        await db.delete_block(canvas_id, block_id)
        removed_blocks.append(dict(block))
        await send_room(canvas_id, f"X;{block_id}")

    if removed_blocks or removed_edges:
        remember(canvas_id, member, {"kind": "many_deleted", "blocks": removed_blocks, "edges": list(removed_edges.values())})


async def undo(canvas_id, member):
    steps = history.get((canvas_id, member["user_id"]))
    if not steps:
        raise Refused("Нечего откатывать")
    step = steps.pop()
    kind = step["kind"]

    if kind == "block_added":
        block = await db.get_block(canvas_id, step["id"])
        if not block or block_line(block) != step["after"]:
            raise Refused(CONFLICT)
        await db.delete_block(canvas_id, step["id"])
        await send_room(canvas_id, f"X;{step['id']}")

    elif kind == "block_changed":
        before = step["before"]
        block = await db.get_block(canvas_id, before["id"])
        if not block or block_line(block) != step["after"]:
            raise Refused(CONFLICT)
        block = await db.update_block(canvas_id, before["id"], before["type"], before["coordinates"], before["text"])
        await send_room(canvas_id, block_line(block))

    elif kind == "block_deleted":
        if await db.get_block(canvas_id, step["block"]["id"]):
            raise Refused(CONFLICT)
        block = await db.restore_block(step["block"])
        await send_room(canvas_id, block_line(block))
        for edge in step["edges"]:
            restored = await db.restore_edge(edge)
            if restored:
                await send_room(canvas_id, edge_line(restored))

    elif kind == "edge_added":
        edge = await db.get_edge(canvas_id, step["id"])
        if not edge or edge_line(edge) != step["after"]:
            raise Refused(CONFLICT)
        await db.delete_edge(canvas_id, step["id"])
        await send_room(canvas_id, f"D;{step['id']}")

    elif kind == "edge_changed":
        edge = await db.get_edge(canvas_id, step["id"])
        if not edge or edge_line(edge) != step["after"]:
            raise Refused(CONFLICT)
        edge = await db.set_label(canvas_id, step["id"], step["before"])
        await send_room(canvas_id, edge_line(edge))

    elif kind == "many_deleted":
        for block in step["blocks"]:
            if await db.get_block(canvas_id, block["id"]):
                raise Refused(CONFLICT)
        for block in step["blocks"]:
            restored = await db.restore_block(block)
            await send_room(canvas_id, block_line(restored))
        for edge in step["edges"]:
            restored = await db.restore_edge(edge)
            if restored:
                await send_room(canvas_id, edge_line(restored))

    elif kind == "edge_deleted":
        restored = await db.restore_edge(step["edge"])
        if not restored:
            raise Refused(CONFLICT)
        await send_room(canvas_id, edge_line(restored))


async def handle(canvas_id, line, member, socket):
    command = line[:1]
    if command == "M":
        await drag_block(canvas_id, line, socket)
        return

    actions = {
        "A": create_block,
        "F": place_block,
        "T": rename_block,
        "Y": retype_block,
        "X": remove_block,
        "E": create_edge,
        "G": label_edge,
        "D": remove_edge,
        "K": remove_many,
    }

    try:
        if command == "Z":
            await undo(canvas_id, member)
        elif command in actions:
            await actions[command](canvas_id, line, member)
    except Refused as error:
        await send_to(canvas_id, socket, f"W;{error}")
