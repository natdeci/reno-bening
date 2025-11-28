from pydantic import BaseModel
from datetime import datetime
class ChatRequest(BaseModel):
    platform_unique_id: str
    query: str
    conversation_id: str = ""
    platform: str
    start_timestamp: datetime