from util.db_connection import get_pool
import datetime

class ChatflowRepository:
    def __init__(self):
        self.history_limit=5
        print("ChatflowRepository Initiated")

    async def create_new_conversation(self, session_id:str, platform:str, user_id:str):
        print(f"Creating new conversation: {session_id}")

        now = datetime.datetime.now()

        query="""
        INSERT INTO bkpm.conversations (id, start_timestamp, platform, platform_unique_id, helpdesk_count)
        VALUES ($1, $2, $3, $4, 0)
        ON CONFLICT (id) DO NOTHING;
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, session_id, now, platform, user_id)
        print("conversation created successfully")

    async def get_greetings(self, greetings_id: int):
        print("Entering get_greetings method")
        query = """
        SELECT greetings_text FROM bkpm.greetings WHERE id=$1
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            greetings = await conn.fetchval(query, greetings_id)
            print("Exiting get_greetings method")
            return greetings
        
    async def get_context(self, session_id: str):
        print("Getting conversation context...")

        if session_id == "":
            print("No conversation context retrieved.")
            return "Conversation History:"

        pool = await get_pool()

        query = """
        SELECT message ->> 'type' AS type, message -> 'data' ->> 'content' AS content
        FROM bkpm.chat_history WHERE session_id = $1
        ORDER BY created_at DESC LIMIT $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, session_id, self.history_limit)
        rows = list(rows)[::-1]

        context_parts = ["Conversation History:"]
        for i, row in enumerate(rows):
            block = f"""
            {i + 1}. type: {row['type']}
            content: {row['content']}
            """
        history_string = "\n".join(context_parts)

        print("Conversation context retrieved!")
        return history_string.strip()
    
    async def increment_helpdesk_count(self, session_id: str):
        print("Entring increment_helpdesk_count method")

        query = """
        UPDATE bkpm.conversations
        SET helpdesk_count = helpdesk_count + 1
        WHERE id = $1;
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, session_id)
        print("Exiting increment_helpdesk_count method")
    
    async def flag_message_cannot_answer(self, session_id:str, question: str):
        print("Entering flag_message_cannot_answer method")
        query = """
        UPDATE bkpm.chat_history
        SET is_cannot_answer = TRUE
        WHERE session_id = $1
            AND message -> 'data' ->> 'content' = $2
            AND message -> 'data' ->> 'type' = 'human';
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, session_id, question)
        print("Exiting flag_message_cannot_answer method")

    async def ingest_category(self, session_id:str, question: str, col_name: str):
        print("Ingesting category for user's question")

        if col_name == "panduan_collection":
            category = "panduan"
        elif col_name == "peraturan_collection":
            category = "peraturan"
        elif col_name == "uraian_collection":
            category = "uraian"
        elif col_name == "faq_collection":
            category = "faq"

        query="""
        UPDATE bkpm.chat_history
        SET category = $1
        WHERE session_id = $2
            AND message -> 'data' ->> 'content' = $3
            AND message -> 'data' ->> 'type' = 'human';
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, category, session_id, question)

        print("Exiting flag_message_cannot_answer method")
        return category
    
    async def check_fail_history(self, session_id:str):
        print("Checking the last chat history...")

        query = """
        SELECT is_cannot_answer
        FROM bkpm.chat_history
        WHERE session_id = $1
          AND message -> 'data' ->> 'type' = 'human'
        ORDER BY created_at DESC
        LIMIT 5;
        """

        pool = await get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, session_id)

        boolean_values = [row["is_cannot_answer"] for row in rows]
        is_all_true = (len(boolean_values) == 5) and all(val is True for val in boolean_values)

        if is_all_true:
            print("5 consecutive messages are tagged as 'Cannot Answer', redirecting...")
        else:
            print("Less than 5 are tagged 'Cannot Answer', continuing conversation...")

        return is_all_true
    
    async def give_conversation_title(self, session_id:str, rewritten:str):
        print("Ingesting category for user's question")
        query = """
            UPDATE bkpm.conversations
            SET context = $1
            WHERE id = $2;
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, rewritten, session_id)
        print("Exiting give_conversation_title method")

    async def ingest_question_category(self, session_id:str, question: str, category: str, sub_category: str):
        print("Ingesting category for user's question")
        query="""
        UPDATE bkpm.chat_history
        SET question_category = $1, question_sub_category = $2
        WHERE session_id = $3
            AND message -> 'data' ->> 'content' = $4
            AND message -> 'data' ->> 'type' = 'human';
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, category, sub_category, session_id, question)

        print(f"session id {session_id} ; question {question}")
        print(f"Message categorized as {category} and {sub_category} successfuly")
        return category, sub_category