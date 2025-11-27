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
human_template = "User Query:{question}"
prompt_template = ChatPromptTemplate.from_messages(
    [
        MessagesPlaceholder(variable_name="history"),
        ("system", """
You are a helpful and expert assistant.
You will receive user query in Bahasa Indonesia
Your task will be to analyze whether the recieved user query is an affirmation or rejection to the question "Apakah anda ingin kami hubungkan ke helpdesk?"

If the user query indicates accept
</instructions>
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

def get_platform_instructions(platform: str) -> str:
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

async def generate_answer(user_query: str, context_docs: list[str], conversation_id: str, platform: str) -> str:
    print("Entering generate_answer method")
    context = "\n\n".join(context_docs)
    platform_instructions = get_platform_instructions(platform)
    result = chain_with_history.invoke(
        {
            "question": user_query,
            "retrieval": context,
            "platform_instructions": platform_instructions
        },
        config={"configurable": {"session_id": conversation_id}},
    )
    print("Exiting generate_answer method")
    return result.content
