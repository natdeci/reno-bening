from pydantic import BaseModel
from typing import List, Dict, Optional

class FinalResponse(BaseModel):
    conversation_id: str = ""
    rewritten_query: str = ""
    answer: str = ""
    citations: List = []
    category: str = ""
    question_category: Optional[Dict] = None
    question_id: int = 0
    answer_id: int = 0
    is_helpdesk: bool = False
    is_answered: bool = False
    is_ask_helpdesk: bool = False
    is_faq: bool = False
    is_feedback: bool = True