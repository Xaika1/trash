from app.database import connection

SCHEMA = """
create table if not exists edges (
    id bigint generated always as identity primary key,
    canvas_id bigint not null references canvases (id) on delete cascade,
    from_block bigint not null references blocks (id) on delete cascade,
    to_block bigint not null references blocks (id) on delete cascade,
    from_side smallint not null,
    to_side smallint not null,
    label text not null default '',
    unique (from_block, from_side, to_block, to_side)
);

create index if not exists edges_canvas on edges (canvas_id);
"""


async def get_all(canvas_id):
    return await connection.pool.fetch("select * from edges where canvas_id = $1 order by id", canvas_id)


async def add(canvas_id, from_block, from_side, to_block, to_side):
    query = """
        insert into edges (canvas_id, from_block, from_side, to_block, to_side)
        select $1, $2, $3, $4, $5
        where (select count(*) from blocks where canvas_id = $1 and id in ($2, $4)) = 2
        on conflict do nothing
        returning *
    """
    return await connection.pool.fetchrow(query, canvas_id, from_block, from_side, to_block, to_side)


async def get(canvas_id, edge_id):
    return await connection.pool.fetchrow("select * from edges where id = $2 and canvas_id = $1", canvas_id, edge_id)


async def get_by_block(canvas_id, block_id):
    query = "select * from edges where canvas_id = $1 and (from_block = $2 or to_block = $2)"
    return await connection.pool.fetch(query, canvas_id, block_id)


async def set_label(canvas_id, edge_id, label):
    query = "update edges set label = $3 where id = $2 and canvas_id = $1 returning *"
    return await connection.pool.fetchrow(query, canvas_id, edge_id, label)


async def restore(edge):
    query = """
        insert into edges (id, canvas_id, from_block, from_side, to_block, to_side, label)
        overriding system value
        select $1, $2, $3, $4, $5, $6, $7
        where (select count(*) from blocks where canvas_id = $2 and id in ($3, $5)) = 2
        on conflict do nothing
        returning *
    """
    return await connection.pool.fetchrow(
        query,
        edge["id"],
        edge["canvas_id"],
        edge["from_block"],
        edge["from_side"],
        edge["to_block"],
        edge["to_side"],
        edge["label"],
    )


async def delete(canvas_id, edge_id):
    await connection.pool.execute("delete from edges where id = $2 and canvas_id = $1", canvas_id, edge_id)
