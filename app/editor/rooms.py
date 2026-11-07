import asyncio

from app import config
from app.editor import history
from app.editor.roles import CLOSED, ROLE_ORDER, role_of

rooms = {}


async def send_to(canvas_id, socket, line):
    try:
        await asyncio.wait_for(socket.send_text(line), config.SEND_TIMEOUT)
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
    history.forget(canvas_id)
