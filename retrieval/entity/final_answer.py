from pydantic import BaseModel
from typing import List, Optional, Tuple

class FinalResponse(BaseModel):
    conversation_id: str = ""
    rewritten_query: str = ""
    category: str = ""
    question_category: Optional[Tuple[str, ...]] = None
    answer: str = ""
    question_id: Optional[int] = 0
    answer_id: Optional[int] = 0
    citations: List = []
    is_helpdesk: bool = False
    is_answered: bool = False
    is_ask_helpdesk: bool = False
    is_faq: bool = False
    is_feedback: bool = True