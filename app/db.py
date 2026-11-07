import os

import asyncpg

pool = None

TABLES = """
create table if not exists blocks (
    id bigint generated always as identity primary key,
    type smallint not null,
    coordinates text not null,
    text text not null default ''
);

create table if not exists edges (
    id bigint generated always as identity primary key,
    from_block bigint not null references blocks (id) on delete cascade,
    to_block bigint not null references blocks (id) on delete cascade,
    from_side smallint not null default 1,
    to_side smallint not null default 3
);

alter table edges add column if not exists from_side smallint not null default 1;
alter table edges add column if not exists to_side smallint not null default 3;
alter table edges drop constraint if exists edges_from_block_to_block_key;
create unique index if not exists edges_sides on edges (from_block, from_side, to_block, to_side);
"""


async def connect():
    global pool
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=10)
    await pool.execute(TABLES)


async def disconnect():
    await pool.close()


async def get_blocks():
    return await pool.fetch("select * from blocks order by id")


async def get_edges():
    return await pool.fetch("select * from edges order by id")


async def count_blocks():
    return await pool.fetchval("select count(*) from blocks")


async def add_block(block_type, coordinates, text):
    query = "insert into blocks (type, coordinates, text) values ($1, $2, $3) returning *"
    return await pool.fetchrow(query, block_type, coordinates, text)


async def move_block(block_id, coordinates):
    query = "update blocks set coordinates = $2 where id = $1 returning *"
    return await pool.fetchrow(query, block_id, coordinates)


async def rename_block(block_id, text):
    query = "update blocks set text = $2 where id = $1 returning *"
    return await pool.fetchrow(query, block_id, text)


async def delete_block(block_id):
    await pool.execute("delete from blocks where id = $1", block_id)


async def add_edge(from_block, from_side, to_block, to_side):
    query = """
        insert into edges (from_block, from_side, to_block, to_side)
        values ($1, $2, $3, $4)
        on conflict do nothing
        returning *
    """
    return await pool.fetchrow(query, from_block, from_side, to_block, to_side)


async def delete_edge(edge_id):
    await pool.execute("delete from edges where id = $1", edge_id)
