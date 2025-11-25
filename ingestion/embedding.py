import time
import os
from typing import List
from langchain_community.vectorstores import Qdrant
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from util.qdrant_connection import vectordb_client
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()

EMBEDDINGS_BASE_URL = os.getenv("OLLAMA_BASE_URL")
EMBEDDINGS_MODEL = os.getenv("EMBED_MODEL")
QDRANT_URL = os.getenv("QDRANT_URL")

embedding_model = OllamaEmbeddings(
    model=EMBEDDINGS_MODEL,
    base_url=EMBEDDINGS_BASE_URL
)
client = vectordb_client


def get_existing_doc_ids(collection_name: str) -> set:
    try:
        scroll_res = client.scroll(
            collection_name=collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )
        ids = set()
        for point in scroll_res[0]:
            payload = point.payload or {}
            doc_id = payload.get("document_id")
            if doc_id:
                ids.add(doc_id)
        return ids
    except Exception as e:
        print(f"Ambil existing IDs di '{collection_name}': {e}")
        return set()

def upsert_documents(
    documents: List[Document],
    category_field: str = "category",
    batch_size: int = 64,
    sleep_time: float = 0.2
):
    
    category_map = {}
    for doc in documents:
        category = doc.metadata.get(category_field, "umum")
        category_map.setdefault(category, []).append(doc)

    for category, docs in category_map.items():
        collection_name = f"{category.replace(' ', '_').lower()}_collection"
        print(f"\nCollection Process '{collection_name}' ({len(docs)} docs)")

        new_docs = docs
        vectorstore = None  
        for i in range(0, len(new_docs), batch_size):
            batch = new_docs[i:i+batch_size]
            print(f"  → Batch Process {i // batch_size + 1} ({len(batch)} docs)...")

            if vectorstore is None:
                vectorstore = Qdrant.from_documents(
                    documents=batch,
                    embedding=embedding_model,
                    url=QDRANT_URL,
                    collection_name=collection_name
                )
            else:
                vectorstore.add_documents(batch)

            time.sleep(sleep_time)

        print(f"Collection '{collection_name}' upserted {len(new_docs)} docs")
