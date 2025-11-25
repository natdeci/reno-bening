import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

vectordb_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    timeout=60.0
)