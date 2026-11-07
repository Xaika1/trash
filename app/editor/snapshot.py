from app.database import blocks, edges
from app.editor.lines import block_line, edge_line


async def send_snapshot(socket, canvas, member, owner):
    await socket.send_text(f"I;title;{canvas['title']}")
    await socket.send_text(f"I;role;{member['role']}")
    await socket.send_text(f"I;id;{canvas['id']}")
    if owner:
        await socket.send_text(f"I;access;{canvas['access']}")
        await socket.send_text(f"I;link;/share/{canvas['share_code']}")
    for block in await blocks.get_all(canvas["id"]):
        await socket.send_text(block_line(block))
    for edge in await edges.get_all(canvas["id"]):
        await socket.send_text(edge_line(edge))
