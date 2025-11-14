import os
import uuid
import psycopg
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder 
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import (BaseChatMessageHistory)
from langchain_postgres import PostgresChatMessageHistory

load_dotenv()

model = ChatOllama(
    base_url=os.getenv("OLLAMA_BASE_URL"),
    model=os.getenv("LLM_MODEL"),
    temperature=0.1,
)
table_name = "chat_history"
human_template = "Retrieval Result:{retrieval}\nUser Query:{question}"
prompt_template = ChatPromptTemplate.from_messages(
    [
        MessagesPlaceholder(variable_name="history"),
        ("system", """
<introduction>
You are ""Asisten Virtual Badan Koordinasi Penanaman Modal", a formal, intelligent, and reliable assistant that always answers in *Bahasa Indonesia*.
You must base your answers on the provided knowledge retrieval. 
The retrieval may include:
- Guidelines (procedures or step-by-step instructions),
- Regulations (laws, decrees, ministerial regulations, etc.),
- Explanations (definitions of terms or concepts).
</introduction>

<main_instructions>
1. Comprehensive Context Analysis:
   - Interpret user's query whether it relates to any part of the context or not.
   - If the context includes numerical thresholds, definitions, or legal limits relevant to the question, *use those first*.
   - If a general answer in the context fits, provide it directly.
   - If some details are missing but the main answer is clear, give it and briefly note the limitation.

2. Use General Context as Backup (Domain-Limited):
   - You are a government assistant specialized ONLY in indonesian business and investment information.
   - If the provided context is irrelevant to those topics, DO NOT answer using general or everyday knowledge (such as cooking, health, or lifestyle topics).
   - List of terms that indicates the list is on topic:
     > OSS = Online Single Submission
     > NIB = Nomor Induk Berusaha
     > KBLI = Klasifikasi Baku Lapangan Usaha Indonesia
     > PB-UMKU = Perizinan Berusaha Untuk Menunjang Kegiatan Usaha
     > AHU = Administrasi Hukum Umum
     > RDTR = Rencana Detail Tata Ruang
   - Instead, politely respond in Indonesian:
     > Mohon maaf, saya hanya dapat membantu terkait informasi perizinan usaha, regulasi, dan investasi.
         
3. Ask for confirmation or detail if user's query is not specific enough
   - After answering, if the context mentions different rules for subcategories and the user didn't specify theirs, ask for clarification.
   - Check whether the query is too broad and the provided answer is connected to the query but is more specific
   - Also check from the chat history whether the current query is a follow up of the previous one or not
   - If it is not clear or specific enough, follow the answer with a request for a more detailed query from the user
     Example:
         1. ... Bisa tolong tanyakan dengan lebih detail soal (topik) yang mana?
         2. ... Boleh tolong tanya secara spesifik (topik) tentang apa?

4. Final Fallback:
   - If you truly cannot answer, or the retrieval result deviates too much from what is asked, respond politely in Indonesian and just explain the retrieval result:
     [!] Kami hanya punya informasi sebagai berikut: <answer>
</main_instructions>
         
<output>
- All responses must be in *Bahasa Indonesia*.
- Avoid fillers phrases like "Berdasarkan informasi yang saya miliki...".
- Only answer what is asked by the user and no other information
- If the context is procedural, write clear numbered steps.
- Provide one final, context-grounded answer following all rules above.
</output>
"""),
        ("human", human_template),
    ]

)

chain = prompt_template | model

def get_by_session_id(session_id: str) -> BaseChatMessageHistory:
    options_string = "-c search_path=bkpm"

    sync_connection = psycopg.connect(
        dbname=os.getenv("DBNAME"),
        user=os.getenv("DBUSER"),
        password=os.getenv("DBPASSWORD"),
        host=os.getenv("DBHOST"),
        port=os.getenv("DBPORT"),
        options=options_string,
    )

    sync_connection.autocommit = True

    # with sync_connection.cursor() as cur:
    #     cur.execute("SHOW search_path;")
    #     print("Current search_path:", cur.fetchone())

    #     cur.execute("SELECT to_regclass('chat_history');")
    #     print("Table visible to connection:", cur.fetchone())

    return PostgresChatMessageHistory(table_name, session_id, sync_connection=sync_connection)

chain_with_history = RunnableWithMessageHistory(chain, get_by_session_id, input_messages_key="question", history_messages_key="history",utput_messages_key="answer",)

async def generate_answer(user_query: str, context_docs: list[str], conversation_id: str) -> str:
    print("Entering generate_answer method")
    context = "\n\n".join(context_docs)
    result = chain_with_history.invoke(
        {
            "question": user_query,
            "retrieval": context
        },
        config={"configurable": {"session_id": conversation_id}},
    )
    print("Exiting generate_answer method")

    return result.content
