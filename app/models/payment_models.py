from pydantic import BaseModel

class MpesaRequest(BaseModel):
    phone_number: str
    plan_name: str
