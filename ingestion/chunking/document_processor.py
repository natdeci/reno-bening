import os
import asyncio
from ingestion.chunking.text_chunker import recursive_chunking
from ingestion.chunking.peraturan_chunker import (
    remove_unwanted_lines,
    split_by_pasal
)

class DocumentProcessor:
    def __init__(self, chunk_size=2000, chunk_overlap=300):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process_text(self, text: str, doc_metadata: dict = None):

        category = (doc_metadata.get("category") or "").lower()

        if category == "peraturan" and "---text---" in text:
            chunks = [text]

        elif category == "peraturan":
            cleaned = remove_unwanted_lines(text)
            chunks = split_by_pasal(
                cleaned,
                filename=doc_metadata.get("filename"),  
                max_chunk_size=self.chunk_size
            )
        else:
            chunks = recursive_chunking(text, self.chunk_size, self.chunk_overlap)

        valid_chunks = [chunk for chunk in chunks if chunk.strip()]
        if not valid_chunks:
            return []

        processed = []
        for chunk in valid_chunks:
            processed.append(self._process_single_chunk(chunk, doc_metadata))
        
        return processed
    
    def _process_single_chunk(self, chunk: str, doc_metadata: dict = None):

        chunk_data = {
            "text": chunk.strip(),
        }

        if doc_metadata:
            chunk_data.update(doc_metadata)
        
        return chunk_data
