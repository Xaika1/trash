from app.database import connection

SCHEMA = """
create table if not exists blocks (
    id bigint generated always as identity primary key,
    canvas_id bigint not null references canvases (id) on delete cascade,
    type smallint not null,
    coordinates text not null,
    text text not null default ''
);

create index if not exists blocks_canvas on blocks (canvas_id);
"""


async def get_all(canvas_id):
    return await connection.pool.fetch("select * from blocks where canvas_id = $1 order by id", canvas_id)


async def count(canvas_id):
    return await connection.pool.fetchval("select count(*) from blocks where canvas_id = $1", canvas_id)


async def add(canvas_id, block_type, coordinates, text):
    query = "insert into blocks (canvas_id, type, coordinates, text) values ($1, $2, $3, $4) returning *"
    return await connection.pool.fetchrow(query, canvas_id, block_type, coordinates, text)


async def get(canvas_id, block_id):
    return await connection.pool.fetchrow("select * from blocks where id = $2 and canvas_id = $1", canvas_id, block_id)


async def update(canvas_id, block_id, block_type, coordinates, text):
    query = """
        update blocks set type = $3, coordinates = $4, text = $5
        where id = $2 and canvas_id = $1
        returning *
    """
    return await connection.pool.fetchrow(query, canvas_id, block_id, block_type, coordinates, text)


async def restore(block):
    query = """
        insert into blocks (id, canvas_id, type, coordinates, text)
        overriding system value
        values ($1, $2, $3, $4, $5)
        returning *
    """
    return await connection.pool.fetchrow(
        query, block["id"], block["canvas_id"], block["type"], block["coordinates"], block["text"]
    )


async def delete(canvas_id, block_id):
    await connection.pool.execute("delete from blocks where id = $2 and canvas_id = $1", canvas_id, block_id)
