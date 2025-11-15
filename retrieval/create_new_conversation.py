import os
import datetime
import psycopg
from dotenv import load_dotenv

load_dotenv()

async def create_new_conversation(session_id:str, platform:str, user_id:str):
    print(f"Creating new conversation: {session_id}")

    now = datetime.datetime.now()
    new_time = now.isoformat(sep=' ', timespec='microseconds')

    conn = psycopg.connect(
        dbname=os.getenv("DBNAME"),
        user=os.getenv("DBUSER"),
        password=os.getenv("DBPASSWORD"),
        host=os.getenv("DBHOST"),
        port=os.getenv("DBPORT"),
    )
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO bkpm.conversations (id, start_timestamp, platform, platform_unique_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """, (session_id, new_time, platform, user_id))
        conn.commit()
    conn.close()

    print("conversation created successfully")
