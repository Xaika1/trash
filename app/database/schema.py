from app.database import blocks, canvases, connection, edges, sessions, users

TABLES = (users, sessions, canvases, blocks, edges)


async def create():
    for table in TABLES:
        await connection.pool.execute(table.SCHEMA)
