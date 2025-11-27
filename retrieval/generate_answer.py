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
1. Comprehensive Retrieval Results Analysis:
   - Interpret user's query whether it relates to any part of the retrieval results or not.
   - If the retrieval results includes numerical thresholds, definitions, or legal limits relevant to the question, *use those first*.
   - If a general answer in the retrieval results fits, provide it directly.
   - If some details are missing but the main answer is clear, give it and briefly note the limitation.

2. Use General Answer as Backup (Domain-Limited):
   - You are a government assistant specialized ONLY in indonesian business and investment information.
   - If the provided retrieval results is irrelevant to those topics, DO NOT answer using general or everyday knowledge (such as cooking, health, or lifestyle topics).
   - Do not answer queries that are about the state of a website service (like an error at a webpage), you are only responsible for the contents and guidelines within it, not the web service.
   - Instead, politely respond in Indonesian:
     > {fail_message}
         
3. Ask for confirmation or detail if user's query is not specific enough
   - After answering, if the retrieval results mentions different rules for subcategories and the user didn't specify theirs, ask for clarification.
   - Check whether the query is too broad and the provided answer is connected to the query but is more specific
   - Also check from the chat history whether the current query is a follow up of the previous one or not
   - If it is not clear or specific enough, follow the answer with a request for a more detailed query from the user
     Example:
         1. ... Bisa tolong tanyakan dengan lebih detail soal (topik) yang mana?
         2. ... Boleh tolong tanya secara spesifik (topik) tentang apa?

4. Final Fallback:
   - If you truly cannot answer, or the retrieval result deviates too much from what is asked, respond politely in Indonesian:
     {fail_message}
</main_instructions>
         
<output>
- All responses must be in *Bahasa Indonesia*.
- Avoid fillers phrases like "Berdasarkan informasi yang saya miliki...".
- Answer only what is asked by the user and do not add more information.
- Use markdown syntax for URLs or links in your response.
- If the knowledge retrieval is procedural, write clear numbered steps.
- Provide one final, context-grounded answer following all rules above.
</output>
         
<platform>
This is an extra instruction about the output too.
{platform_instructions}
</platform>
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
    return PostgresChatMessageHistory(table_name, session_id, sync_connection=sync_connection)

chain_with_history = RunnableWithMessageHistory(chain, get_by_session_id, input_messages_key="question", history_messages_key="history",utput_messages_key="answer",)

async def get_platform_instructions(platform: str) -> str:
    platform = platform.lower()
    if platform in ["instagram", "email", "whatsapp"]:
        return (
            "Do NOT use any markdown formatting (no **bold**, no *, no #, no lists with dashes). "
            "Output must be plain text only, but still structured and readable. "
            "For lists, use multiple lines like:\n"
            "- First item\n"
            "- Second item\n"
            "But do NOT include markdown symbols; instead:\n"
            "1. First item\n"
            "2. Second item\n"
            "or\n"
            "First item\nSecond item\nThird item"
        )
    return (
        "You may use Markdown formatting (lists, bold text, code blocks) "
        "to structure your response cleanly."
    )

async def get_fail_message(status: bool) -> str:
    if status:
        return "Mohon maaf, pertanyaan tersebut belum bisa kami jawab. Silakan ajukan pertanyaan lain. Untuk bantuan lebih lanjut, apakah anda ingin dihubungkan ke helpdesk agen layanan?"
    else:
        return "Mohon maaf, saya hanya dapat membantu terkait informasi perizinan usaha, regulasi, dan investasi. Mungkin Bapak/Ibu bisa tanyakan dengan lebih detail dan jelas?"

async def generate_answer(user_query: str, context_docs: list[str], conversation_id: str, platform: str, status: bool) -> str:
    print("Entering generate_answer method")
    context = "\n\n".join(context_docs)
    platform_instructions = await get_platform_instructions(platform)
    fail_message = await get_fail_message(status)
    result = chain_with_history.invoke(
        {
            "question": user_query,
            "retrieval": context,
            "fail_message": fail_message,
            "platform_instructions": platform_instructions
        },
        config={"configurable": {"session_id": conversation_id}},
    )
    print("Exiting generate_answer method")
    return result.content
