import os
import asyncpg

DBNAME=os.getenv("DBNAME")
DBUSER=os.getenv("DBUSER")
DBPASSWORD=os.getenv("DBPASSWORD")
DBHOST=os.getenv("DBHOST")
DBPORT=os.getenv("DBPORT")

DB_URL = f"postgresql://{DBUSER}:{DBPASSWORD}@{DBHOST}:{DBPORT}/{DBNAME}"

pool = None

async def init_db():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=20)

async def close_db():
    global pool
    if pool:
        await pool.close()

async def get_pool():
    global pool
    if pool is None:
        await init_db()
    return pool