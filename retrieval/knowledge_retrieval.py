import os
import requests
from dotenv import load_dotenv
import asyncio
from typing import List, Iterable
import re
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client.models import SparseVector
from util.qdrant_connection import vectordb_client

load_dotenv()

TOP_K = int(os.getenv("TOP_K"))
BM25_URL = os.getenv("BM25_URL")

embedding_model = OllamaEmbeddings(
    model=os.getenv("EMBED_MODEL"),
    base_url=os.getenv("OLLAMA_BASE_URL")
)
def extract_kbli(query: str):
    match = re.search(r'\b\d{5}\b', query)
    return match.group(0) if match else None

def build_kbli_filter(kbli_code: str):
    return {
        "must": [
            {"key": "page_content", "match": {"text": "Ruang Lingkup"}},
            {"key": "page_content", "match": {"text": f"Kode: KBLI {kbli_code}"}}
        ]
    }

class BM25SparseEmbeddings:
    def __init__(self, bm25_url: str):
        self.bm25_url = bm25_url

    def _convert_to_sparse_vector(self, vector_data) -> SparseVector:
        if vector_data is None:
            return SparseVector(indices=[], values=[])
        
        if isinstance(vector_data, dict):
            indices = vector_data.get("indices", [])
            values = vector_data.get("values", [])
        elif isinstance(vector_data, list) and vector_data and isinstance(vector_data[0], (list, tuple)):
            indices = [int(idx) for idx, _ in vector_data]
            values = [float(val) for _, val in vector_data]
        else:
            print(f"Unexpected vector format: {type(vector_data)}")
            return SparseVector(indices=[], values=[])
        
        return SparseVector(indices=indices, values=values)

    def embed_documents(self, texts: list[str]) -> list:
        try:
            response = requests.post(self.bm25_url, json={"texts": texts})
            response.raise_for_status()
            vectors = response.json().get("vectors", [])
            return [self._convert_to_sparse_vector(v) for v in vectors]
        except Exception as e:
            print("BM25 batch retrieval error:", e)
            return [SparseVector(indices=[], values=[]) for _ in texts]

    def embed_query(self, text: str):
        try:
            response = requests.post(self.bm25_url, json={"texts": [text]})
            response.raise_for_status()
            vectors = response.json().get("vectors", [])
            if vectors:
                return self._convert_to_sparse_vector(vectors[0])
            return SparseVector(indices=[], values=[])
        except Exception as e:
            print("BM25 retrieval error:", e)
            return SparseVector(indices=[], values=[])
        
sparse_embeddings = BM25SparseEmbeddings(BM25_URL)

async def retrieve_knowledge(user_query: str, collection_name: str, top_k: int = TOP_K):
    print("Entering retrieve_knowledge method")
    print(f"Collection: {collection_name}")

    kbli_code = extract_kbli(user_query)
    loop = asyncio.get_event_loop()

    def sync_search():
        vectorstore = QdrantVectorStore(
            client=vectordb_client,
            collection_name=collection_name,
            embedding=embedding_model,         
            sparse_embedding=sparse_embeddings,  
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",
        )

        if kbli_code:
            filter_body = build_kbli_filter(kbli_code)
            results = vectorstore.similarity_search_with_score(
                query=user_query,
                k=top_k,
                filter=filter_body
            )
        else:
            results = vectorstore.similarity_search_with_score(
                query=user_query,
                k=top_k
            )

        if collection_name == "peraturan_collection":
            results = [
                (doc, score) for doc, score in results
                if "Cukup jelas." not in doc.page_content
            ]

        return results

    results = await loop.run_in_executor(None, sync_search)
    print(results)
    print("Exiting retrieve_knowledge method")
    return results

async def retrieve_knowledge_faq(user_query: str, collection_name: str, top_k: int = TOP_K):
    print("Entering retrieve_knowledge_faq method")
    print(f"Collection: {collection_name}")

    loop = asyncio.get_event_loop()

    def sync_search():
        vectorstore = QdrantVectorStore(
            client=vectordb_client,
            collection_name="qna_collection",
            embedding=embedding_model,         
            retrieval_mode=RetrievalMode.DENSE,
            vector_name="dense",
        )

        return vectorstore.similarity_search_with_score(
            query=user_query,
            k=top_k,
        )

    results = await loop.run_in_executor(None, sync_search)
    print("Exiting retrieve_knowledge_faq method")
    return results