import os
import requests
from dotenv import load_dotenv
from util.async_ollama import ollama_chat_async
from util.inference_limiter import ollama_semaphore

load_dotenv()

model_name = os.getenv("LLM_MODEL")
model_temperature = 0.0
prompt = """
<introduction>
Your role is to act as an expert query rewriter. 
Your task is to rewrite the given <user_query> into a more concise, complete, and effective query for knowledge retrieval.

You will also receive <context>, which represents previous topic history.
You MUST first determine whether the <user_query> is still related to the <context>.
</introduction>

<key_terms>
KEY TERMS (DO NOT MODIFY THESE TERMS. KEEP EXACT SPELLING):
OSS, LKPM, NIB, KBLI, PB, PB-UMKU, AHU, RDTR
</key_terms>

<connection_rules>
A <user_query> is considered RELATED to the <context> if:
- They share the same main topic, OR
- The <user_query> is a continuation, additional detail, clarification, or follow-up to the topic in the <context>, OR
- The <user_query> cannot be fully understood without information from the <context>.

If NONE of these conditions are met, consider the <user_query> as a new standalone topic.
</connection_rules>

<instructions>
- Both input and output will be in Bahasa Indonesia.
- Your output must contain ONLY the rewritten query, with no explanation or commentary.
- If the <user_query> IS RELATED to the <context>, you MUST include relevant keywords from the <context> in the rewritten query.
- If the <user_query> is NOT related, you MUST NOT use the <context> at all.
- If the <context> is empty, ignore it and use only the <user_query>.
- The rewritten query must be concise, efficient, and focus only on the essential intent.
- Do NOT answer the user's question. ONLY rewrite it.
- You MUST output in Bahasa Indonesia
</instructions>
"""

async def rewrite_query(user_query: str, history_context: str) -> str:
    async with ollama_semaphore:
        print("Entering rewrite_query method")

        user = f"""
        {prompt}

        <context>
        {history_context}
        </context>

        <user_query>
        {user_query}
        </user_query>
        """

        response = await ollama_chat_async(
            model=model_name,
            messages=[
                # {"role": "system", "content": prompt},
                {"role": "user", "content": user}
            ],
            options={"temperature": float(model_temperature)},
            stream=False
        )

        print("Exiting rewrite_query method")
        return response["message"]["content"].strip()
