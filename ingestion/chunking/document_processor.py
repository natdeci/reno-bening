import os
import asyncio
from ingestion.handler.llm_handler import LLMHandler
from ingestion.chunking.text_chunker import recursive_chunking

class DocumentProcessor:
    def __init__(self, llm_handler=None, chunk_size=2000, chunk_overlap=300):
        self.llm_handler = llm_handler or LLMHandler()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def process_text(self, text: str, doc_metadata: dict = None):
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