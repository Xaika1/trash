from app import config
from app.database import blocks, edges
from app.editor.history import remember
from app.editor.lines import block_line, to_coordinates, to_id, to_point, to_type
from app.editor.rooms import send_room


async def create_block(canvas_id, line, member):
    _, block_type, x, y, width, height, text = line.split(";", 6)
    if len(text) > config.MAX_TEXT or await blocks.count(canvas_id) >= config.MAX_BLOCKS:
        return
    block = await blocks.add(canvas_id, to_type(block_type), to_coordinates(x, y, width, height), text)
    remember(canvas_id, member, {"kind": "block_added", "id": block["id"], "after": block_line(block)})
    await send_room(canvas_id, block_line(block))


async def drag_block(canvas_id, line, sender):
    _, block_id, x, y = line.split(";")
    await send_room(canvas_id, f"M;{to_id(block_id)};{to_point(x)};{to_point(y)}", skip=sender)


async def change_block(canvas_id, block_id, member, block_type=None, coordinates=None, text=None):
    old = await blocks.get(canvas_id, block_id)
    if not old:
        return
    new = await blocks.update(
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
    if len(text) <= config.MAX_TEXT:
        await change_block(canvas_id, to_id(block_id), member, text=text)


async def retype_block(canvas_id, line, member):
    _, block_id, block_type = line.split(";")
    await change_block(canvas_id, to_id(block_id), member, block_type=to_type(block_type))


async def remove_block(canvas_id, line, member):
    _, block_id = line.split(";")
    block = await blocks.get(canvas_id, to_id(block_id))
    if not block:
        return
    block_edges = await edges.get_by_block(canvas_id, block["id"])
    await blocks.delete(canvas_id, block["id"])
    remember(canvas_id, member, {"kind": "block_deleted", "block": dict(block), "edges": [dict(edge) for edge in block_edges]})
    await send_room(canvas_id, f"X;{block['id']}")
