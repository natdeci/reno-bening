import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

async def give_conversation_title(session_id:str, rewritten:str):
    print("Ingesting category for user's question")

    conn = psycopg.connect(
        dbname=os.getenv("DBNAME"),
        user=os.getenv("DBUSER"),
        password=os.getenv("DBPASSWORD"),
        host=os.getenv("DBHOST"),
        port=os.getenv("DBPORT"),
    )
    
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE bkpm.conversations
            SET context = %s
            WHERE id = %s;
        """, (rewritten, session_id))
        conn.commit()
    conn.close()

    print(f"session id {session_id}: title {rewritten}")
