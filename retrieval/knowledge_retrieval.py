import os
from dotenv import load_dotenv
from util.qdrant_connection import vectordb_client

load_dotenv()

async def retrieve_knowledge(query_vector: list[float], collection_name: str):
    print("Entering retrieve_knowledge method")
    results = await vectordb_client.search(
        collection_name= collection_name,
        query_vector=query_vector,
        limit=os.getenv('TOP_K')
    )
    print("Exiting retrieve_knowledge method")
    return [hit.payload for hit in results]
