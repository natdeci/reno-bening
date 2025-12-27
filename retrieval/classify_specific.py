import os
from dotenv import load_dotenv
from util.async_ollama import ollama_chat_async

load_dotenv()

model_name = os.getenv("LLM_MODEL")
model_temperature = os.getenv("OLLAMA_TEMPERATURE")
prompt = """
You are a KBLI Question Type Classifier.
Classify each user query as either 'specific' or 'general':
- specific: user provides detailed info about the business (type, target, facilities, etc.)
- general: user provides vague or broad description only

Only output one word: 'specific' or 'general'.

FEW-SHOT EXAMPLES:

USER: Aku mau buka usaha hotel
ASSISTANT: general

USER: Saya mau buka villa harian, kode KBLI apa yang cocok?
ASSISTANT: specific

USER: Saya mau buka hotel, kode KBLI apa yang cocok?
ASSISTANT: general

USER: Buka penginapan kblinya berapa ya?
ASSISTANT: general

USER: saya mau buka hotel bintang 4, kode KBLI
ASSISTANT: specific

USER: Restoran cepat saji
ASSISTANT: general

USER: Saya ingin membuka apartemen hotel dengan luas 60000 hektare, kode KBLI yang tepat?
ASSISTANT: specific

NOTE: You will receive <context> which is the chat history between you and this user. Check <context> to determine whether the <query> is already sufficient or not
"""

async def classify_specific(user_query: str, history_context: str) -> str:
    print("Entering classify_specific method")
    user_content = f"""
    {prompt}

    <context>
    {history_context}
    </context>

    <query>
    {user_query}
    </query>
    """

    try:
        response = await ollama_chat_async(
            model=model_name,
            messages=[
                # {"role": "system", "content": prompt},
                {"role": "user", "content": user_content}
            ],
            options={"temperature": float(model_temperature)},
        )
        print("Exiting classify_specific method")
        return response["message"]["content"].strip()
    except Exception as e:
        print("Error in classify_specific:", e)
        return "Terjadi kesalahan saat mengklasifikasikan KBLI."
