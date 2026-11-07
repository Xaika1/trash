from app.database import blocks, edges
from app.editor import history
from app.editor.lines import block_line, edge_line
from app.editor.rooms import send_room

CONFLICT = "Нельзя откатить: это уже изменил кто-то другой"


class Refused(Exception):
    pass


async def restore_edges(canvas_id, saved_edges):
    for edge in saved_edges:
        restored = await edges.restore(edge)
        if restored:
            await send_room(canvas_id, edge_line(restored))


async def undo_block_added(canvas_id, step):
    block = await blocks.get(canvas_id, step["id"])
    if not block or block_line(block) != step["after"]:
        raise Refused(CONFLICT)
    await blocks.delete(canvas_id, step["id"])
    await send_room(canvas_id, f"X;{step['id']}")


async def undo_block_changed(canvas_id, step):
    before = step["before"]
    block = await blocks.get(canvas_id, before["id"])
    if not block or block_line(block) != step["after"]:
        raise Refused(CONFLICT)
    block = await blocks.update(canvas_id, before["id"], before["type"], before["coordinates"], before["text"])
    await send_room(canvas_id, block_line(block))


async def undo_block_deleted(canvas_id, step):
    if await blocks.get(canvas_id, step["block"]["id"]):
        raise Refused(CONFLICT)
    block = await blocks.restore(step["block"])
    await send_room(canvas_id, block_line(block))
    await restore_edges(canvas_id, step["edges"])


async def undo_edge_added(canvas_id, step):
    edge = await edges.get(canvas_id, step["id"])
    if not edge or edge_line(edge) != step["after"]:
        raise Refused(CONFLICT)
    await edges.delete(canvas_id, step["id"])
    await send_room(canvas_id, f"D;{step['id']}")


async def undo_edge_changed(canvas_id, step):
    edge = await edges.get(canvas_id, step["id"])
    if not edge or edge_line(edge) != step["after"]:
        raise Refused(CONFLICT)
    edge = await edges.set_label(canvas_id, step["id"], step["before"])
    await send_room(canvas_id, edge_line(edge))


async def undo_many_deleted(canvas_id, step):
    for block in step["blocks"]:
        if await blocks.get(canvas_id, block["id"]):
            raise Refused(CONFLICT)
    for block in step["blocks"]:
        restored = await blocks.restore(block)
        await send_room(canvas_id, block_line(restored))
    await restore_edges(canvas_id, step["edges"])


async def undo_edge_deleted(canvas_id, step):
    restored = await edges.restore(step["edge"])
    if not restored:
        raise Refused(CONFLICT)
    await send_room(canvas_id, edge_line(restored))


UNDO_ACTIONS = {
    "block_added": undo_block_added,
    "block_changed": undo_block_changed,
    "block_deleted": undo_block_deleted,
    "edge_added": undo_edge_added,
    "edge_changed": undo_edge_changed,
    "many_deleted": undo_many_deleted,
    "edge_deleted": undo_edge_deleted,
}


async def undo(canvas_id, member):
    step = history.take_last(canvas_id, member)
    if not step:
        raise Refused("Нечего откатывать")
    await UNDO_ACTIONS[step["kind"]](canvas_id, step)
