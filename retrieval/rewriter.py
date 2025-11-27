import os
import requests
from dotenv import load_dotenv

load_dotenv()

async def rewrite_query(user_query: str, history_context: str) -> str:
    print("Entering rewrite_query method")

    prompt = f"""
<introduction>
Your role will be as an expert query rewriter, whose task is to rephrase or remake the given <user_query> into a more concise and effective query for a knowledge retrieval. You will also receive a <context> in case the <user_query> needs more context to be rewritten.
</introduction>

<instructions>
- Your input will be in Bahasa Indonesia.
- Output only the rewritten query and nothing else.
- The output must be in Bahasa Indonesia.
- New query must be efficient and contains every important words.
- If user's query is too short or not detailed enough, use the given <context> to help you rephrase.
- You may not use the given <context> if the query is clear enough.
- You may not use the given <context> if it is blank.
- Do not make the new query an answer to the original query, even if the answer is in the context. Just rewrite the query.
- You must adhere to every instructions.
</instructions>
"""
    user = f"""
<context>
{history_context}
</context>

<user_query>
{user_query}
</user_query>
"""

    payload = {
        "model": os.getenv('LLM_MODEL'),
        "messages": [
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": user
            }
        ],
        "stream": False,
    }

    response = requests.post(f"{os.getenv('OLLAMA_BASE_URL')}api/chat", json=payload)
    response.raise_for_status()
    data = response.json()
    print("Exiting rewrite_query method")
    message = data.get("message", {})
    return message.get("content", "").strip()