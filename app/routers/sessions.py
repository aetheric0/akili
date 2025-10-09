from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.security import get_current_user_token
from app.services.db import cache_service
from app.models.session_model import SessionInfo
from app.security import get_current_user_token

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.get(
    "/",
    summary="Get all sessions for the current user",
    response_model=List[SessionInfo]
)
async def get_user_sessions(
    guest_token: str = Depends(get_current_user_token)
):
    """
    Retrieves a list of all chat sessions associated with
    the user's guest token.
    """
    try:
        # 1. Get all session IDs from the user's Set in Redis
        session_ids = cache_service.smembers(f"user:{guest_token}")

        if not session_ids:
            return []

        sessions_list = []

        # 2. Loop through each session ID to get its details
        for session_id in session_ids:
            session_data = cache_service.hgetall(f"session:{session_id}")
            if session_data:
                sessions_list.append(
                    SessionInfo(
                        id=session_id,
                        document_name=session_data.get("document_name", "Unknown Document"),
                        created_at=session_data.get("created_at", "")
                    )
                )

        # Optional: Sort sessions by creation date
        sessions_list.sort(key=lambda s: s.created_at, reverse=True)

        return sessions_list

    except Exception as e:
        print(f"Error fetching sessions for user {guest_token}: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve user sessions.")
