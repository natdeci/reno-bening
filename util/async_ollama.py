import os
import asyncio
from util.ollama_client import ollama_client
from dotenv import load_dotenv

load_dotenv()
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT"))

async def ollama_chat_async(timeout: float = OLLAMA_TIMEOUT, **kwargs):
    return await asyncio.wait_for(
        asyncio.to_thread(ollama_client.chat, **kwargs),
        timeout=timeout
    )

async def async_embed(text: str, timeout: float = OLLAMA_TIMEOUT):
    return await asyncio.wait_for(
        asyncio.to_thread(
            ollama_client.embeddings,
            model=os.getenv("EMBED_MODEL"),
            prompt=text
        ),
        timeout=timeout
    )
