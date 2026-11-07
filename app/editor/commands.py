from app.editor.blocks import create_block, drag_block, place_block, remove_block, rename_block, retype_block
from app.editor.edges import create_edge, label_edge, remove_edge
from app.editor.rooms import send_to
from app.editor.selection import remove_many
from app.editor.undo import Refused, undo

ACTIONS = {
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


async def handle(canvas_id, line, member, socket):
    command = line[:1]
    if command == "M":
        await drag_block(canvas_id, line, socket)
        return
    try:
        if command == "Z":
            await undo(canvas_id, member)
        elif command in ACTIONS:
            await ACTIONS[command](canvas_id, line, member)
    except Refused as error:
        await send_to(canvas_id, socket, f"W;{error}")
