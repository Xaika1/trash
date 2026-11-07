from app.database import connection

SCHEMA = """
create table if not exists sessions (
    token_hash text primary key,
    user_id bigint not null references users (id) on delete cascade,
    expires_at timestamptz not null
);
"""


async def add(token_hash, user_id, days):
    query = "insert into sessions (token_hash, user_id, expires_at) values ($1, $2, now() + make_interval(days => $3))"
    await connection.pool.execute(query, token_hash, user_id, days)


async def get_user(token_hash):
    query = """
        select users.id, users.login
        from sessions
        join users on users.id = sessions.user_id
        where sessions.token_hash = $1 and sessions.expires_at > now()
    """
    return await connection.pool.fetchrow(query, token_hash)


async def delete(token_hash):
    await connection.pool.execute("delete from sessions where token_hash = $1", token_hash)
