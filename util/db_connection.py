import os
from dotenv import load_dotenv
from urllib.parse import quote
import asyncpg

load_dotenv()

DBNAME=os.getenv("DBNAME")
DBUSER=os.getenv("DBUSER")
DBPASSWORD=quote(os.getenv("DBPASSWORD"), safe="")
DBHOST=os.getenv("DBHOST")
DBPORT=os.getenv("DBPORT")

DB_URL = f"postgresql://{DBUSER}:{DBPASSWORD}@{DBHOST}:{DBPORT}/{DBNAME}"

pool = None

async def init_db():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=30, timeout=60.0)

async def close_db():
    global pool
    if pool:
        await pool.close()

async def get_pool():
    global pool
    if pool is None:
        await init_db()
    return pool

def pool_stats(pool):
    size = pool.get_size() # total opened connections
    idle = pool.get_idle_size() # idle connections
    in_use = size - idle

    return {
        "size": size,
        "idle": idle,
        "in_use": in_use,
    }
