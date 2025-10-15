from pydantic import BaseModel
from .chat_models import ChatMessage
from typing import List

class SessionInfo(BaseModel):
    id: str
    document_name: str
    created_at: str


class SessionDetail(SessionInfo):
    history: List[ChatMessage]

