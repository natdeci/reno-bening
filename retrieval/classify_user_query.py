import os 
import json
import re
import requests
from dotenv import load_dotenv
from util.db_connection import get_pool
from util.async_ollama import ollama_chat_async
from util.inference_limiter import ollama_semaphore

load_dotenv()

model_name = os.getenv("LLM_MODEL")
model_temperature = os.getenv("OLLAMA_TEMPERATURE")

async def load_classifications_from_db():
    pool = await get_pool()

    query = """
      SELECT category, sub_category, detail
      FROM bkpm.user_query_classifications
      ORDER BY category, sub_category;
   """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    
    categories = {}
    for r in rows:
        cat = r["category"]
        sub = r["sub_category"]

        if cat not in categories:
            categories[cat] = []
        if sub not in categories[cat]:
            categories[cat].append(sub)

    return categories

async def classify_user_query(user_query: str) -> dict:
    print("Entering classify_user_query...")

    categories = await load_classifications_from_db()
    categories_json = json.dumps(categories, ensure_ascii=False, indent=2)

   
    system_prompt = f"""
    You are a classification assistant for BKPM Indonesia's OSS system.

    CRITICAL RULES:
    1. You MUST respond with ONLY a JSON object - no markdown, no explanations
    2. You MUST use categories EXACTLY from the list below - DO NOT create new categories and sub categories
    3. Format: {{ "category": "exact_name", "sub_category": "exact_name" }}
    4. DETAIL is ONLY context to help you classify - DO NOT use DETAIL text as sub_category

    KEY TERMS:
    - OSS = Online Single Submission (Indonesian government licensing platform)
    - NIB = Nomor Induk Berusaha (official bussiness identity)
    - KBLI = Klasifikasi Baku Lapangan Usaha Indonesia
    - PB-UMKU = Perizinan Berusaha Untuk Menunjang Kegiatan Usaha
    - AHU = Administrasi Hukum Umum (Kementerian Hukum dan HAM)
    - RDTR = Rencana Detail Tata Ruang

    AVAILABLE_CATEGORIES:
    {categories_json}
    """

    user_prompt = f"""
    {system_prompt}

    User query: "{user_query}"

    Remember: Output ONLY the JSON object, use EXACT category names from the list.
    """

    async with ollama_semaphore:
        try:
            response = await ollama_chat_async(
                model=model_name,
                messages=[
                    # {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={"temperature": float(model_temperature)},
                format="json",
                stream=False
            )

            content = response["message"]["content"].strip()

            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content).strip()

            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            result = json.loads(content)

            if "category" not in result or "sub_category" not in result:
                raise ValueError("Missing required JSON fields.")

            print("Classification OK:", result)
            return result

        except Exception as e:
            print("Classification error:", e)
            print("Raw model output:", content)
            return {
                "category": "Unknown",
                "sub_category": "Unknown"
            }
        