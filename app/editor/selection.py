from app.database import blocks, edges
from app.editor.history import remember
from app.editor.lines import to_ids
from app.editor.rooms import send_room


async def remove_many(canvas_id, line, member):
    _, block_text, edge_text = line.split(";")
    removed_blocks = []
    removed_edges = {}

    for edge_id in to_ids(edge_text):
        edge = await edges.get(canvas_id, edge_id)
        if edge:
            removed_edges[edge["id"]] = dict(edge)
            await edges.delete(canvas_id, edge["id"])
            await send_room(canvas_id, f"D;{edge['id']}")

    for block_id in to_ids(block_text):
        block = await blocks.get(canvas_id, block_id)
        if not block:
            continue
        for edge in await edges.get_by_block(canvas_id, block_id):
            removed_edges[edge["id"]] = dict(edge)
        await blocks.delete(canvas_id, block_id)
        removed_blocks.append(dict(block))
        await send_room(canvas_id, f"X;{block_id}")

    if removed_blocks or removed_edges:
        remember(canvas_id, member, {"kind": "many_deleted", "blocks": removed_blocks, "edges": list(removed_edges.values())})
