# import os
# from FlagEmbedding import FlagReranker

# reranker = FlagReranker(os.getenv("RERANK_MODEL"), use_fp16=True)

# async def rerank_documents_with_flag(query, docs, top_k=3):
#     try:
#         pairs = [[query, doc] for doc in docs]
#         rerank_scores = reranker.compute_score(pairs, normalize=True)
#         reranked = []
#         for idx, doc in enumerate(docs):
#             rerank_score = rerank_scores[idx]
#             reranked.append((doc, rerank_score))
#         reranked.sort(key=lambda x: x[1], reverse=True)
#         reranked_content = []
#         for reranked_payload in reranked:
#             reranked_content.append(reranked_payload[0])
#         return reranked_content[:top_k]
#     except Exception as e:
#         print(f"Reranking error: {str(e)}, using original scores")
#         return docs[:top_k]

import os
from FlagEmbedding import FlagReranker

reranker = FlagReranker(os.getenv("RERANK_MODEL"), use_fp16=True)

async def rerank_documents_with_flag(query, docs, filenames, top_k=3):
    try:
        doc_file_pairs = list(zip(docs, filenames))
        pairs = [[query, doc] for doc in docs]
        rerank_scores = reranker.compute_score(pairs, normalize=True)
        reranked = []
        for idx, (doc, filename) in enumerate(doc_file_pairs):
            rerank_score = rerank_scores[idx]
            reranked.append(((doc, filename), rerank_score))
        reranked.sort(key=lambda x: x[1], reverse=True)
        reranked_docs = []
        reranked_filenames = []
        for i in range(min(top_k, len(reranked))):
            ((doc, filename), score) = reranked[i]
            reranked_docs.append(doc)
            if filename not in reranked_filenames:
                reranked_filenames.append(filename)
        return reranked_docs, reranked_filenames
    except Exception as e:
        print(f"Reranking error: {str(e)}, using original scores")
        return docs[:top_k], filenames[:top_k]