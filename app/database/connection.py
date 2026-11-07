import asyncpg

from app import config

pool = None


async def connect():
    global pool
    pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=config.DB_POOL_MIN, max_size=config.DB_POOL_MAX)


async def disconnect():
    await pool.close()


async def ping():
    await pool.fetchval("select 1")
