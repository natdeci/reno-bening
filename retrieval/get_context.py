import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
limit = 5

async def get_context(session_id: str):
    print("Getting conversation context...")

    if session_id == "":
        return "Conversation History:"

    conn = psycopg.connect(
        dbname=os.getenv("DBNAME"),
        user=os.getenv("DBUSER"),
        password=os.getenv("DBPASSWORD"),
        host=os.getenv("DBHOST"),
        port=os.getenv("DBPORT"),
    )

    query = f"""
    SELECT
        message ->> 'type' AS type,
        message -> 'data' ->> 'content' AS content
    FROM bkpm.chat_history
    WHERE session_id = %s
    ORDER BY created_at DESC
    LIMIT %s;
    """

    results = []
    with conn.cursor() as cur:
        cur.execute(query, (session_id, limit))
        results = cur.fetchall()

    conn.close()

    context_parts = ["Conversation History:"]
    results = results[::-1]
    
    for i, (msg_type, content) in enumerate(results):
        block = f"""
{i + 1}. type: {msg_type}
   content: {content}
"""
        context_parts.append(block)
    
    history_string = "\n".join(context_parts)

    print("Conversation context retrieved! ")
    # print("===========================\n" + history_string.strip())
    return history_string.strip()