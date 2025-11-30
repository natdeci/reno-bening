from util.db_connection import get_pool
import datetime
import pytz
import json

class ChatflowRepository:
    def __init__(self):
        self.history_limit=6
        print("ChatflowRepository Initiated")

    async def create_new_conversation(self, session_id:str, platform:str, user_id:str):
        print(f"Creating new conversation: {session_id}")

        now = datetime.datetime.now()

        query="""
        INSERT INTO bkpm.conversations (id, start_timestamp, platform, platform_unique_id, is_ask_helpdesk)
        VALUES ($1, $2, $3, $4, false)
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
        ORDER BY id DESC LIMIT $2
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
            context_parts.append(block)
        history_string = "\n".join(context_parts)
        print(history_string.strip())
        print("Conversation context retrieved!")
        return history_string.strip()
    
    async def change_is_helpdesk(self, session_id: str):
        print("Entering change_is_helpdesk method")

        query = """
        UPDATE bkpm.conversations
        SET is_helpdesk = TRUE
        WHERE id =$1;
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, session_id)
        print("Exiting change_is_helpdesk method")
    
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

    async def ingest_skipped_question(self, session_id: str, message: str, category: str, sub_category: str):
        print("Entering ingest_skipped_question method")
        now = datetime.datetime.now()

        query="""
        INSERT INTO bkpm.chat_history_outside_oss (session_id, message, question_category, question_sub_category, created_at)
        VALUES ($1, $2, $3, $4, $5);
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, session_id, message, category, sub_category, now)
        print("Exiting ingest_skipped_question method")

    async def get_revision(self, id: int):
        print("Entring get_revision method")

        query = """
        SELECT revision FROM bkpm.chat_history WHERE id = $1
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            revision = await conn.fetchval(query, id)
            print("Exiting get_revision method")
            return revision
        
    async def flag_message_is_answered(self, session_id: str, question: str):
        print("Entering flag_message_is_answered method")
        query = """
        UPDATE bkpm.chat_history
        SET is_answered = TRUE
        WHERE id = (
            SELECT id FROM bkpm.chat_history
            WHERE session_id = $1
                AND message -> 'data' ->> 'content' = $2
                AND message -> 'data' ->> 'type' = 'human'
            ORDER BY id DESC
            LIMIT 1
        );
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, session_id, question)
        print("Exiting flag_message_is_answered method")
    
    async def flag_message_cannot_answer(self, session_id:str, question: str):
        print("Entering flag_message_cannot_answer method")
        query = """
        UPDATE bkpm.chat_history
        SET is_cannot_answer = TRUE
        WHERE id = (
            SELECT id FROM bkpm.chat_history
            WHERE session_id = $1
                AND message -> 'data' ->> 'content' = $2
                AND message -> 'data' ->> 'type' = 'human'
            ORDER BY id DESC
            LIMIT 1
        );
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, session_id, question)
        print("Exiting flag_message_cannot_answer method")

    async def ingest_category(self, session_id:str, question: str, col_name: str):
        print("Ingesting category for user's question")
        print(f"session_id: {session_id}")
        print(f"question: {question}")
        print(f"col_name: {col_name}")

        if col_name == "panduan_collection":
            category = "panduan"
        elif col_name == "peraturan_collection":
            category = "peraturan"
        elif col_name == "uraian_collection":
            category = "uraian"
        elif col_name == "faq_collection":
            category = "faq"
        print(category)
        query="""
        UPDATE bkpm.chat_history
        SET category = $1
        WHERE id = (
            SELECT id FROM bkpm.chat_history
            WHERE session_id = $2
                AND message -> 'data' ->> 'content' = $3
                AND message -> 'data' ->> 'type' = 'human'
            ORDER BY id DESC
            LIMIT 1
        );
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, category, session_id, question)

        print("Exiting ingest_category method")
        return category
    
    async def check_fail_history(self, session_id:str):
        print("Checking the last chat history...")

        query = """
        SELECT is_cannot_answer
        FROM bkpm.chat_history
        WHERE session_id = $1
          AND message -> 'data' ->> 'type' = 'human'
        ORDER BY created_at DESC
        LIMIT 4;
        """

        pool = await get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, session_id)

        boolean_values = [row["is_cannot_answer"] for row in rows]
        is_all_true = (len(boolean_values) == 4) and all(val is True for val in boolean_values)

        if is_all_true:
            print("4 consecutive messages are tagged as 'Cannot Answer', redirecting...")
        else:
            print("Less than 4 are tagged 'Cannot Answer', continuing conversation...")

        return is_all_true
    
    async def give_conversation_title(self, session_id:str, rewritten:str):
        print("Ingesting category for user's question")
        query = """
            UPDATE bkpm.conversations
            SET context = $1
            WHERE id = $2
            AND context IS NULL;
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
        WHERE id = (
            SELECT id FROM bkpm.chat_history
            WHERE session_id = $3
                AND message -> 'data' ->> 'content' = $4
                AND message -> 'data' ->> 'type' = 'human'
            ORDER BY id DESC
            LIMIT 1
        );
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, category, sub_category, session_id, question)

        print(f"Message categorized as {category} and {sub_category} successfuly")
        return category, sub_category
    
    async def ingest_citations(self, citations: list, session_id:str, question: str):
        print("Entering ingest_citations method...")

        citations_dict = [{"id": cid, "name": cname} for cid, cname in citations]
        json_str = json.dumps(citations_dict)

        query="""
        UPDATE bkpm.chat_history
        SET citation = $1
        WHERE id = (
            SELECT id FROM bkpm.chat_history
            WHERE session_id = $2
                AND message -> 'data' ->> 'content' = $3
                AND message -> 'data' ->> 'type' = 'human'
            ORDER BY id DESC
            LIMIT 1
        );
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, json_str, session_id, question)
        print("Exiting ingest_citations method...")

    async def change_is_ask_helpdesk_status(self, session_id: str):
        print("Entering change_is_helpdesk_status method...")

        query="""
        UPDATE bkpm.conversations
        SET is_ask_helpdesk = NOT is_ask_helpdesk
        WHERE id = $1;
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, session_id)
        print("Exiting change_is_helpdesk_status method...")

    async def check_is_ask_helpdesk(self, session_id: str):
        print("Entering check_is_ask_helpdesk method")

        query="""
        SELECT is_ask_helpdesk
        FROM bkpm.conversations
        WHERE id = $1;
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            is_ask_helpdesk = await conn.fetchval(query, session_id)
        print("Exiting check_is_ask_helpdesk method")
        return is_ask_helpdesk
    
    async def ingest_created_at_chat_history(self, session_id: str, question: str):
        print("Entering ingest_created_at method")

        tz = pytz.timezone("Asia/Jakarta")
        jakarta_now = datetime.datetime.now(tz).replace(tzinfo=None)

        query="""
        WITH target AS (
            SELECT id 
            FROM bkpm.chat_history
            WHERE session_id = $2
            AND message -> 'data' ->> 'content' = $3
            AND message -> 'data' ->> 'type' = 'human'
            ORDER BY id DESC
            LIMIT 1
        )
        UPDATE bkpm.chat_history
        SET created_at = $1
        WHERE id IN (
            (SELECT id FROM target),
            (SELECT id + 1 FROM target)
        );
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, jakarta_now, session_id, question)

        print("Exiting ingest_created_at method")

    async def get_helpdesk_operation_status(self):
        print("Entering get_helpdesk_operation_status method")

        query = """
        SELECT description, time_info FROM operation_time
        WHERE description IN ('start_time', 'stop_time')
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)

        op = {row["description"]: row["time_info"] for row in rows}
        start = op["start_time"]
        stop = op["stop_time"]
        jakarta = pytz.timezone("Asia/Jakarta")
        now_time = datetime.now(jakarta).time()

        print("Exiting get_helpdesk_operation_status method")
        return start <= now_time <= stop
    
    async def ingest_end_timestamp(self, session_id: str):
        print("Entering ingest_end_timestamp method")

        tz = pytz.timezone("Asia/Jakarta")
        jakarta_now = datetime.datetime.now(tz).replace(tzinfo=None)

        query = """
        UPDATE bkpm.conversations
        SET end_timestamp = $1
        WHERE id = $2
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, jakarta_now, session_id)

        print("Exiting ingest_end_timestamp method")

    async def ingest_start_timestamp(self, session_id: str, start_timestamp: datetime):

        query = """
        UPDATE bkpm.chat_history
        SET start_timestamp = $1
        WHERE id IN (
            SELECT id
            FROM bkpm.chat_history
            WHERE session_id = $2
            AND start_timestamp IS NULL
            ORDER BY created_at DESC
            LIMIT 2
        );
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, start_timestamp, session_id)

        print("Start timestamp successfully ingested")

    async def get_chat_history_id(self, session_id: str, question: str):
        print("Entering get_chat_history_id method")

        query="""
        SELECT id, id + 1 AS answer_id
        FROM bkpm.chat_history
        WHERE session_id = $1
        AND message -> 'data' ->> 'content' = $2
        AND message -> 'data' ->> 'type' = 'human'
        ORDER BY id DESC
        LIMIT 1
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, session_id, question)

        if not rows:
            return None, None
        
        row = rows[0]
        print("Exiting get_chat_history_id method")
        return row["id"], row["answer_id"]
    
    async def check_is_helpdesk(self, session_id: str):
        print("Entering check_is_helpdesk method")

        query="""
        SELECT is_helpdesk
        FROM bkpm.conversations
        WHERE id = $1;
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            is_ask_helpdesk = await conn.fetchval(query, session_id)
        print("Exiting check_is_helpdesk method")
        return is_ask_helpdesk