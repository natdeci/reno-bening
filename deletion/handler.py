import os
import aiohttp
from dotenv import load_dotenv
from util.qdrant_connection import vectordb_client

load_dotenv()

class ChunkDeletionHandler:
    def __init__(self):
        self.client = vectordb_client
        print("ChunkDeletionHandler initialized")

    async def delete_points_by_file_id(self, file_id_value: str, category: str):
        try:
            url = f"{os.getenv('QDRANT_URL')}/collections/{category}_collection/points/delete/"
            payload = {
                "filter": {
                    "must": [
                        {
                            "key": "metadata.file_id",
                            "match": {"value": file_id_value}
                        }
                    ]
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    return await resp.json()

        except Exception as e:
            print(f"❌ An error occurred during deletion: {e}")
            return None
