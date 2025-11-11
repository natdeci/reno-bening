import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from ingestion.prompts.llm_prompts import TOPIC_PROMPT_TEMPLATE, DESCRIPTION_PROMPT_TEMPLATE

load_dotenv()

class LLMHandler:
    def __init__(self, model=None, base_url=None, temperature=None):
        self.model = model or os.getenv("LLM_MODEL")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        self.temperature = temperature or float(os.getenv("LLM_TEMPERATURE", 0.0))

    async def _call_llm_api(self, prompt: str, session: aiohttp.ClientSession) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": self.temperature
        }
        
        try:
            async with session.post(
                f"{self.base_url}api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=600)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("response", "").strip()
        except Exception as e:
            print(f"[ERROR calling LLM]: {e}")
            return ""
    
    async def extract_document_info(self, text_chunk: str):
        topic_prompt = TOPIC_PROMPT_TEMPLATE.format(chunk_text=text_chunk[:1000])
        description_prompt = DESCRIPTION_PROMPT_TEMPLATE.format(chunk_text=text_chunk[:1000])

        async with aiohttp.ClientSession() as session:
            topic, description = await asyncio.gather(
                self._call_llm_api(topic_prompt, session),
                self._call_llm_api(description_prompt, session)
            )
        
        return topic, description