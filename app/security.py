"""
Extracts the Guest Pass Token from the Authorization Header
"""

from fastapi import Header, HTTPException

async def get_current_user_token(authorization: str = Header(...)) -> str:
    """
    Extacts and validates the guest pass token from the Authorization header.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")

    token = authorization.split(" ")[1]
    if not token:
        raise HTTPException(status_code=401, detail="Missing Guest Token")

    return token
