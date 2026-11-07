from app.database import connection

SCHEMA = """
create table if not exists users (
    id bigint generated always as identity primary key,
    login text not null unique,
    password_hash text not null,
    created_at timestamptz not null default now()
);
"""


async def add(login, password_hash):
    query = "insert into users (login, password_hash) values ($1, $2) on conflict do nothing returning id, login"
    return await connection.pool.fetchrow(query, login, password_hash)


async def get_by_login(login):
    return await connection.pool.fetchrow("select * from users where login = $1", login)
