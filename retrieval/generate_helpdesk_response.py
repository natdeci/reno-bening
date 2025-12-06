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
    temperature=os.getenv("OLLAMA_TEMPERATURE"),
)

class LimitedPostgresHistory(PostgresChatMessageHistory):
    def __init__(self, table_name, session_id, sync_connection, max_messages=6):
        super().__init__(table_name, session_id, sync_connection=sync_connection)
        self.max_messages = max_messages

    @property
    def messages(self):
        """Return only the last N messages."""
        all_msgs = super().messages
        limited = all_msgs[-self.max_messages:]

        return limited

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
        {helpdesk_response}
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
    return LimitedPostgresHistory(table_name, session_id, sync_connection, max_messages=6)

chain_with_history = RunnableWithMessageHistory(chain, get_by_session_id, input_messages_key="question", history_messages_key="history",utput_messages_key="answer")

def get_helpdesk_response(helpdesk_active_status: bool):
    helpdesk_response = ""
    if helpdesk_active_status:
        helpdesk_response = "Percakapan ini akan dihubungkan ke agen layanan."
    else:
        helpdesk_response = "Mohon maaf, untuk saat ini helpdesk agen layanan kami sedang tidak tersedia.\nBapak/Ibu bisa ajukan pertanyaan dengan mengirim email ke kontak@oss.go.id"

    return helpdesk_response

def generate_helpdesk_response(user_query: str, conversation_id: str, helpdesk_active_status: bool) -> str:
    print("Entering generate_helpdesk_response method")
    helpdesk_response = get_helpdesk_response(helpdesk_active_status)
    result = chain_with_history.invoke(
        {
            "question": user_query,
            "helpdesk_response": helpdesk_response
        },
        config={"configurable": {"session_id": conversation_id}},
    )
    print("Exiting generate_helpdesk_response method")
    return result.content
