import os
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
        Your task will be to respond a user query, which is a request to be connected into a helpdesk service.

        You may output your response:
        Percakapan ini akan dihubungkan ke agen layanan.
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

chain_with_history = RunnableWithMessageHistory(chain, get_by_session_id, input_messages_key="question", history_messages_key="history",utput_messages_key="answer")

async def generate_helpdesk_response(user_query: str, conversation_id: str) -> str:
    print("Entering generate_helpdesk_response method")
    result = chain_with_history.invoke(
        {
            "question": user_query,
        },
        config={"configurable": {"session_id": conversation_id}},
    )
    print("Exiting generate_helpdesk_response method")
    return result.content
