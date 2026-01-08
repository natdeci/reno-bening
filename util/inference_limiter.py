import asyncio

OLLAMA_MAX_CONCURRENCY = 1
ollama_semaphore = asyncio.Semaphore(OLLAMA_MAX_CONCURRENCY)