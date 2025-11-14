import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

async def check_fail_history(session_id:str):
    print("Checking the last chat history...")

    conn = psycopg.connect(
        dbname=os.getenv("DBNAME"),
        user=os.getenv("DBUSER"),
        password=os.getenv("DBPASSWORD"),
        host=os.getenv("DBHOST"),
        port=os.getenv("DBPORT"),
    )

    query = f"""
    SELECT is_cannot_answer
    FROM bkpm.chat_history
    WHERE session_id = %s
    ORDER BY created_at DESC
    LIMIT 4;
    """

    results = []
    with conn.cursor() as cur:
        cur.execute(query, (session_id,))
        results = cur.fetchall()
    conn.close()

    boolean_values = [row[0] for row in results]

    is_all_true = (len(boolean_values) == 4) and all(val is True for val in boolean_values)

    if is_all_true:
        print("5 consecutive messages is tagged as 'Cannot Answer', redirecting into helpdesk...")
    else:
        print("5 consecutive messages is not tagged as 'Cannot Answer', continuing conversation...")

    return is_all_true