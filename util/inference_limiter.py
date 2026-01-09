import os
import asyncio

OLLAMA_MAX_CONCURRENCY = int(os.getenv("SEMAPHORE_NUM"))
ollama_semaphore = asyncio.Semaphore(OLLAMA_MAX_CONCURRENCY)