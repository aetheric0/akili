from pydantic import BaseModel

class StudySessionRequest(BaseModel):
    session_id: str
