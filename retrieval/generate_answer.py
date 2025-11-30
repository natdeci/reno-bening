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
    temperature=os.getenv("OLLAMA_TEMPERATURE"),
)
table_name = "chat_history"
human_template = "Retrieval Result:{retrieval}\nUser Query:{question}\nCitation Prefix:{citation_prefix}"
prompt_template = ChatPromptTemplate.from_messages(
    [
        MessagesPlaceholder(variable_name="history"),
        ("system", """
You are "Asisten Virtual Badan Koordinasi Penanaman Modal", a formal, intelligent, and reliable assistant that always answers in Bahasa Indonesia.

The response must be based on the provided retrieval results. The retrieval may contain:
• Guidelines
• Regulations or laws
• Concepts and explanations

MAIN INSTRUCTIONS
1. Analyze whether the user query relates to the retrieval results.
2. If the retrieval contains numerical values, legal thresholds, business terms, or definitions relevant to the question, always prioritize those.
3. If the retrieval provides a general answer that fits the question, use it.
4. If some details are missing but the main answer is clear, answer using available information and briefly note the missing part.
5. Your domain is ONLY Indonesian business, licensing, investment, and related regulations. Do not answer general knowledge such as lifestyle, cooking, medicine, everyday motivation, or unrelated topics.

WHEN YOU MUST NOT ANSWER
• If retrieval is unrelated to business, licenses, investment or regulations
• If the question is about the website status (errors, outages, menus not showing, login problems)

In these cases respond politely in Bahasa Indonesia using the provided fallback message: {fail_message}

CLARIFYING WHEN NEEDED
If the user's question is too broad or not specific, or the retrieval refers to multiple situations and the user did not specify one, ask for clarification at the end of the answer.

FORMAT RULES
• All responses must be in Bahasa Indonesia.
• If citation_prefix is not empty, start your answer with it.
• Do not use any Markdown formatting (no *, **, _, #, >, lists, bullets, tables, code blocks, emojis, or special styling). Use only plain sentences and line breaks.
• Write all numbers without separators. For example: 10000, not 10,000 or 10.000. If the retrieval contains separators, rewrite the number without separators.
• Answer only what is asked. Do not add extra topics.
         
PLATFORM INSTRUCTIONS (OVERRIDES WHEN APPLICABLE)
These instructions depend on the platform and will be inserted here: {platform_instructions}
If the platform instructions conflict with any rule above, follow the platform instructions.

ABOUT THIS PROMPT
The formatting and symbols used above are ONLY for internal structuring of instructions. They are NOT examples of formatting for your answer. Do not repeat or imitate any of the formatting found in this prompt.

FINAL ENFORCEMENT
If your internal initial draft violates any formatting rules, do not show the incorrect draft. Fix it silently and output only the final corrected version. Do not apologize or explain the correction.
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
        print("==Output shouldn't be in markdown==")
        return (
            "- You must not use any Markdown formatting in your replies. Do not use symbols for styling such as *, **, __, ```, #, >, or code blocks."
            "Reply only in plain text."
            "The only allowed formatting is line breaks to separate paragraphs or lines."
            "Do not add any other formatting or syntax. Ignore the formatting style used in these instructions. It is only for structuring the rules."
            "Do not treat it as an example format for your answers."
        )
    return (
        "- You may use Markdown formatting (lists, bold text, code blocks) "
        "to structure your response cleanly."
    )

async def get_fail_message(status: bool) -> str:
    if status:
        return "Mohon maaf, pertanyaan tersebut belum bisa kami jawab. Silakan ajukan pertanyaan lain. Untuk bantuan lebih lanjut, apakah anda ingin dihubungkan ke helpdesk agen layanan?"
    else:
        return "Mohon maaf, saya hanya dapat membantu terkait informasi perizinan usaha, regulasi, dan investasi. Mungkin Bapak/Ibu bisa tanyakan dengan lebih detail dan jelas?"

async def generate_answer(user_query: str, context_docs: list[str], conversation_id: str, platform: str, status: bool, collection_choice: str | None = None, citation_str: str | None = None) -> str:
    print("Entering generate_answer method")
    citation_prefix = ""
    if collection_choice == "peraturan_collection":
        citation_prefix = f"Menurut {citation_str},"
    context = "\n\n".join(context_docs)
    platform_instructions = await get_platform_instructions(platform)
    print(f"Platform Instruction: {platform_instructions}")
    fail_message = await get_fail_message(status)
    result = chain_with_history.invoke(
        {
            "question": user_query,
            "retrieval": context,
            "fail_message": fail_message,
            "platform_instructions": platform_instructions,
            "citation_prefix": citation_prefix
        },
        config={"configurable": {"session_id": conversation_id}},
    )
    print("Exiting generate_answer method")
    return result.content
