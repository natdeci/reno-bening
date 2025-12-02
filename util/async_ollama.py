import os
import asyncio
from util.ollama_client import ollama_client

async def ollama_chat_async(**kwargs):
    return await asyncio.to_thread(ollama_client.chat, **kwargs)

async def async_embed(text: str):
    return await asyncio.to_thread(
        ollama_client.embeddings,
        model=os.getenv("EMBED_MODEL"),
        prompt=text
    )