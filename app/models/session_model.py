from pydantic import BaseModel

class SessionInfo(BaseModel):
    id: str
    document_name: str
    created_at: str
