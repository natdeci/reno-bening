import os
import asyncio
from util.ollama_client import ollama_client

async def ollama_chat_async(timeout: float = 300.0, **kwargs):
    return await asyncio.wait_for(
        asyncio.to_thread(ollama_client.chat, **kwargs),
        timeout=timeout
    )

async def async_embed(text: str, timeout: float = 120.0):
    return await asyncio.wait_for(
        asyncio.to_thread(
            ollama_client.embeddings,
            model=os.getenv("EMBED_MODEL"),
            prompt=text
        ),
        timeout=timeout
    )