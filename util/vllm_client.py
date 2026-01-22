import os
import httpx
from dotenv import load_dotenv


load_dotenv()

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL")
VLLM_MODEL = os.getenv("VLLM_MODEL")

VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT"))
async def vllm_chat_async(messages, temperature=0.0):
    async with httpx.AsyncClient(timeout=VLLM_TIMEOUT) as client:
        response = await client.post(
            f"{VLLM_BASE_URL}/v1/chat/completions",
            json={
                "model": VLLM_MODEL,
                "messages": messages,
                "temperature": temperature
            }
        )
        data = response.json()
        print(type(data["choices"][0]["message"]["content"]))
        return data["choices"][0]["message"]["content"]