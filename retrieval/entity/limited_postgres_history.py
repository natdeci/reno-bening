from langchain_postgres import PostgresChatMessageHistory

class LimitedPostgresHistory(PostgresChatMessageHistory):
    def __init__(self, table_name, session_id, sync_connection, max_messages=6):
        super().__init__(table_name, session_id, sync_connection=sync_connection)
        self.max_messages = max_messages

    @property
    def messages(self):
        """Return only the last N messages."""
        all_msgs = super().messages
        limited = all_msgs[-self.max_messages:]
        # print("=====")
        # print(limited)
        # print("=====")
        return limited