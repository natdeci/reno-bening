import os
import time
import requests
from typing import List
from dotenv import load_dotenv
from util.qdrant_connection import vectordb_client
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import models
from qdrant_client.models import SparseVector
from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams

load_dotenv()

EMBEDDINGS_MODEL = os.getenv("EMBED_MODEL")
EMBEDDINGS_BASE_URL = os.getenv("OLLAMA_BASE_URL")
QDRANT_URL = os.getenv("QDRANT_URL")
BM25_URL = os.getenv("BM25_URL")
DENSE_VECTOR_SIZE = 2560

embedding_model = OllamaEmbeddings(
    model=EMBEDDINGS_MODEL,
    base_url=EMBEDDINGS_BASE_URL
)

class BM25SparseEmbedder:
    def __init__(self, url: str):
        self.url = url

    def embed_documents(self, texts: list[str]):
        try:
            response = requests.post(self.url, json={"texts": texts})
            response.raise_for_status()
            raw_vectors = response.json()["vectors"]

            processed = []
            for v in raw_vectors:

                indices = v.get("indices", [])
                values = v.get("values", [])

                processed.append(
                    SparseVector(
                        indices=indices,
                        values=values
                    )
                )

            return processed

        except Exception as e:
            print("Error from BM25:", e)
            return [
                SparseVector(indices=[], values=[])
                for _ in texts
            ]

    def embed_query(self, text: str):
        return self.embed_documents([text])[0]

sparse_embedder = BM25SparseEmbedder(BM25_URL)

def upsert_documents(
    documents: List[Document],
    category_field: str = "category",
    batch_size: int = 64,
    sleep_time: float = 0.2
):
    client = vectordb_client
    existing_collections = [c.name for c in client.get_collections().collections]

    category_map = {}
    for doc in documents:
        cat = doc.metadata.get(category_field, "umum")
        category_map.setdefault(cat, []).append(doc)

    for category, docs in category_map.items():

        collection_name = f"{category.replace(' ', '_').lower()}_collection"
        print(f"\nProcessing collection '{collection_name}' ({len(docs)} chunks)")

        if collection_name not in existing_collections:
            client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(size=DENSE_VECTOR_SIZE, distance=Distance.COSINE)
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(index=models.SparseIndexParams(on_disk=False))
                },
            )

        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embedding_model,
            sparse_embedding=sparse_embedder,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",
        )

        for i in range(0, len(docs), batch_size):
            batch = docs[i:i+batch_size]
            print(f"  → Batch {i//batch_size + 1} ({len(batch)})")

            try:
                vectorstore.add_documents(batch)
                print("    ✓ success")
            except Exception as e:
                print("    ✗ error:", e)

            time.sleep(sleep_time)

        print(f"✔ Done: {collection_name}")
