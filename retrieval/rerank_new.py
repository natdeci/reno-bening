from dotenv import load_dotenv
import httpx
import os

load_dotenv()
API_URL = os.getenv("RERANK_URL")

async def rerank_documents(query, docs, fileids, filenames, top_k=3):
    print("Entering rerank_documents_with_flag method")

    payload = {
        "query": query,
        "docs": docs,
        "fileids": fileids,
        "filenames": filenames
    }

    try:
        async with httpx.AsyncClient(timeout=600) as client:
            response = await client.post(API_URL, json=payload)
        response.raise_for_status()

        response_list = response.json()
        reranked_docs, reranked_fileids, reranked_filenames = response_list

        print("Exiting rerank_documents_with_flag method")
        return reranked_docs, reranked_fileids, reranked_filenames
    except Exception as e:
        print(f"Reranking error: {str(e)}, using original scores")
        return docs[:top_k], fileids[:top_k], filenames[:top_k]
