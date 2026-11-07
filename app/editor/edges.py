from app import config
from app.database import edges
from app.editor.history import remember
from app.editor.lines import edge_line, to_id, to_side
from app.editor.rooms import send_room


async def create_edge(canvas_id, line, member):
    _, from_block, from_side, to_block, to_side_value = line.split(";")
    from_block = to_id(from_block)
    to_block = to_id(to_block)
    if from_block == to_block:
        return
    edge = await edges.add(canvas_id, from_block, to_side(from_side), to_block, to_side(to_side_value))
    if edge:
        remember(canvas_id, member, {"kind": "edge_added", "id": edge["id"], "after": edge_line(edge)})
        await send_room(canvas_id, edge_line(edge))


async def label_edge(canvas_id, line, member):
    _, edge_id, label = line.split(";", 2)
    old = await edges.get(canvas_id, to_id(edge_id))
    if not old or len(label) > config.MAX_LABEL:
        return
    new = await edges.set_label(canvas_id, old["id"], label)
    if new["label"] != old["label"]:
        remember(canvas_id, member, {"kind": "edge_changed", "before": old["label"], "id": old["id"], "after": edge_line(new)})
    await send_room(canvas_id, edge_line(new))


async def remove_edge(canvas_id, line, member):
    _, edge_id = line.split(";")
    edge = await edges.get(canvas_id, to_id(edge_id))
    if not edge:
        return
    await edges.delete(canvas_id, edge["id"])
    remember(canvas_id, member, {"kind": "edge_deleted", "edge": dict(edge)})
    await send_room(canvas_id, f"D;{edge['id']}")
