import os
import secrets

import asyncpg

pool = None

TABLES = """
create table if not exists users (
    id bigint generated always as identity primary key,
    login text not null unique,
    password_hash text not null,
    created_at timestamptz not null default now()
);

create table if not exists sessions (
    token_hash text primary key,
    user_id bigint not null references users (id) on delete cascade,
    expires_at timestamptz not null
);

create table if not exists canvases (
    id bigint generated always as identity primary key,
    owner_id bigint not null references users (id) on delete cascade,
    title text not null,
    share_code text not null unique,
    access smallint not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists blocks (
    id bigint generated always as identity primary key,
    canvas_id bigint not null references canvases (id) on delete cascade,
    type smallint not null,
    coordinates text not null,
    text text not null default ''
);

create table if not exists edges (
    id bigint generated always as identity primary key,
    canvas_id bigint not null references canvases (id) on delete cascade,
    from_block bigint not null references blocks (id) on delete cascade,
    to_block bigint not null references blocks (id) on delete cascade,
    from_side smallint not null,
    to_side smallint not null,
    unique (from_block, from_side, to_block, to_side)
);

create index if not exists canvases_owner on canvases (owner_id);
create index if not exists blocks_canvas on blocks (canvas_id);
create index if not exists edges_canvas on edges (canvas_id);
"""


async def connect():
    global pool
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=10)
    await pool.execute(TABLES)


async def disconnect():
    await pool.close()


async def ping():
    await pool.fetchval("select 1")


async def add_user(login, password_hash):
    query = "insert into users (login, password_hash) values ($1, $2) on conflict do nothing returning id, login"
    return await pool.fetchrow(query, login, password_hash)


async def get_user_by_login(login):
    return await pool.fetchrow("select * from users where login = $1", login)


async def add_session(token_hash, user_id, days):
    query = "insert into sessions (token_hash, user_id, expires_at) values ($1, $2, now() + make_interval(days => $3))"
    await pool.execute(query, token_hash, user_id, days)


async def get_session_user(token_hash):
    query = """
        select users.id, users.login
        from sessions
        join users on users.id = sessions.user_id
        where sessions.token_hash = $1 and sessions.expires_at > now()
    """
    return await pool.fetchrow(query, token_hash)


async def delete_session(token_hash):
    await pool.execute("delete from sessions where token_hash = $1", token_hash)


async def get_canvases(owner_id):
    return await pool.fetch("select * from canvases where owner_id = $1 order by id desc", owner_id)


async def get_canvas(canvas_id):
    return await pool.fetchrow("select * from canvases where id = $1", canvas_id)


async def get_canvas_by_code(code):
    return await pool.fetchrow("select * from canvases where share_code = $1", code)


async def add_canvas(owner_id, title):
    query = "insert into canvases (owner_id, title, share_code) values ($1, $2, $3) returning *"
    return await pool.fetchrow(query, owner_id, title, secrets.token_urlsafe(9))


async def rename_canvas(canvas_id, title):
    return await pool.fetchrow("update canvases set title = $2 where id = $1 returning *", canvas_id, title)


async def set_access(canvas_id, access):
    return await pool.fetchrow("update canvases set access = $2 where id = $1 returning *", canvas_id, access)


async def delete_canvas(canvas_id):
    await pool.execute("delete from canvases where id = $1", canvas_id)


async def get_blocks(canvas_id):
    return await pool.fetch("select * from blocks where canvas_id = $1 order by id", canvas_id)


async def get_edges(canvas_id):
    return await pool.fetch("select * from edges where canvas_id = $1 order by id", canvas_id)


async def count_blocks(canvas_id):
    return await pool.fetchval("select count(*) from blocks where canvas_id = $1", canvas_id)


async def add_block(canvas_id, block_type, coordinates, text):
    query = "insert into blocks (canvas_id, type, coordinates, text) values ($1, $2, $3, $4) returning *"
    return await pool.fetchrow(query, canvas_id, block_type, coordinates, text)


async def move_block(canvas_id, block_id, coordinates):
    query = "update blocks set coordinates = $3 where id = $2 and canvas_id = $1 returning *"
    return await pool.fetchrow(query, canvas_id, block_id, coordinates)


async def rename_block(canvas_id, block_id, text):
    query = "update blocks set text = $3 where id = $2 and canvas_id = $1 returning *"
    return await pool.fetchrow(query, canvas_id, block_id, text)


async def delete_block(canvas_id, block_id):
    await pool.execute("delete from blocks where id = $2 and canvas_id = $1", canvas_id, block_id)


async def add_edge(canvas_id, from_block, from_side, to_block, to_side):
    query = """
        insert into edges (canvas_id, from_block, from_side, to_block, to_side)
        select $1, $2, $3, $4, $5
        where (select count(*) from blocks where canvas_id = $1 and id in ($2, $4)) = 2
        on conflict do nothing
        returning *
    """
    return await pool.fetchrow(query, canvas_id, from_block, from_side, to_block, to_side)


async def delete_edge(canvas_id, edge_id):
    await pool.execute("delete from edges where id = $2 and canvas_id = $1", canvas_id, edge_id)
