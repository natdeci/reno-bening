import os
from dotenv import load_dotenv
from util.async_ollama import async_embed

load_dotenv()

async def convert_to_embedding(user_query: str):
    print("Entering convert_to_embedding method")
    query_vector = await async_embed(user_query)

    print("Exiting convert_to_embedding method")
    return query_vector["embedding"]