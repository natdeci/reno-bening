import os
from dotenv import load_dotenv
from util.async_ollama import ollama_chat_async

load_dotenv()

model_name = os.getenv("LLM_MODEL")
model_temperature = os.getenv("OLLAMA_TEMPERATURE")
prompt = """
<introduction>
You are an expert AI assistant for classifying customer questions about business and industry in Indonesia.
Your task is to determine whether a user's question is related to KBLI (Klasifikasi Baku Lapangan Usaha Indonesia) or not.
The user query will be in Bahasa Indonesia.
You will receive <user_query> to classify.
</introduction>

<guide>
Rules:
- If the question is about KBLI codes, business field classification, type of business, or persyaratan (requirements) per jenis usaha, classify as "kbli".
- If the question is general about starting a business, tips, procedures, or tutorials without asking classification/category/requirements, classify as "non-kbli".
- Only output "kbli" or "non-kbli".
- Treat questions about business category, izin, dokumen usaha, atau persyaratan per usaha sebagai "kbli", even if the user does not mention "KBLI" explicitly.

Few-shot examples:

1. Pertanyaan: "Kode KBLI untuk usaha jasa pengiriman barang apa?"
   Jawaban: kbli

2. Pertanyaan: "Aku mau buka restoran, kategori usaha apa yang harus aku pilih?"
   Jawaban: kbli

3. Pertanyaan: "Aku mau buka usaha online, apa yang harus disiapkan?"
   Jawaban: non-kbli

4. Pertanyaan: "Jenis usaha toko baju apa yang sesuai untuk perizinan?"
   Jawaban: kbli

5. Pertanyaan: "Bagaimana cara mendaftarkan perusahaan saya di OSS?"
   Jawaban: non-kbli

6. Pertanyaan: "Usahaku bergerak di jasa logistik, masuk kategori KBLI apa?"
   Jawaban: kbli

7. Pertanyaan: "Aku ingin buka kafe, bagaimana cara memulainya?"
   Jawaban: non-kbli

8. Pertanyaan: "Persyaratan dokumen untuk usaha pengasinan buah apa saja?"
   Jawaban: kbli

9. Pertanyaan: "Apa tips memulai usaha kecil di rumah?"
   Jawaban: non-kbli

10. Pertanyaan: "Untuk membuka usaha makanan olahan, izin apa yang perlu saya urus?"
    Jawaban: kbli

11. Pertanyaan: "Aku mau buka toko online, bagaimana cara memulainya?"
    Jawaban: non-kbli

12. Pertanyaan: "Usaha produksi pakaian masuk kategori KBLI apa?"
    Jawaban: kbli

13. Pertanyaan: "Apa saja langkah awal untuk memulai bisnis kuliner?"
    Jawaban: non-kbli

14. Pertanyaan: "Dokumen apa yang dibutuhkan untuk membuka pabrik pengolahan makanan?"
    Jawaban: kbli

15. Pertanyaan: "Aku ingin membuka restoran kecil, apa yang harus dilakukan dulu?"
    Jawaban: non-kbli

</guide>

<output>
Output:
- Only return "kbli" or "non-kbli" based on the <user_query>.
</output>

<instructions>
- Input will be in Bahasa Indonesia.
- Strictly follow the guide and examples.
- DO NOT output anything else other than "kbli" or "non-kbli".
- Consider intent, not just keywords: if user asks about category, classification, or requirements for a business type, treat as "kbli".
</instructions>
"""

async def classify_kbli(user_query: str, history_context: str) -> str:
    print("Entering classify_kbli method")
    user_content = f"""
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
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content, "options": {"temperature": model_temperature}}
            ]
        )
        print("Exiting classify_kbli method")
        return response["message"]["content"].strip()
    except Exception as e:
        print("Error in classify_kbli:", e)
        return "Terjadi kesalahan saat mengklasifikasikan KBLI."
