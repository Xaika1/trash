import secrets

from app import config
from app.database import connection

SCHEMA = """
create table if not exists canvases (
    id bigint generated always as identity primary key,
    owner_id bigint not null references users (id) on delete cascade,
    title text not null,
    share_code text not null unique,
    access smallint not null default 0,
    created_at timestamptz not null default now()
);

create index if not exists canvases_owner on canvases (owner_id);
"""


async def get_by_owner(owner_id):
    return await connection.pool.fetch("select * from canvases where owner_id = $1 order by id desc", owner_id)


async def get(canvas_id):
    return await connection.pool.fetchrow("select * from canvases where id = $1", canvas_id)


async def get_by_code(code):
    return await connection.pool.fetchrow("select * from canvases where share_code = $1", code)


async def add(owner_id, title):
    query = "insert into canvases (owner_id, title, share_code) values ($1, $2, $3) returning *"
    return await connection.pool.fetchrow(query, owner_id, title, secrets.token_urlsafe(config.SHARE_CODE_BYTES))


async def rename(canvas_id, title):
    return await connection.pool.fetchrow("update canvases set title = $2 where id = $1 returning *", canvas_id, title)


async def set_access(canvas_id, access):
    return await connection.pool.fetchrow("update canvases set access = $2 where id = $1 returning *", canvas_id, access)


async def delete(canvas_id):
    await connection.pool.execute("delete from canvases where id = $1", canvas_id)
