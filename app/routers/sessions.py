"""
Sessions Endpoint
-----------------
Handles retrieval of user chat sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.security import get_current_user
from app.services.db import cache_service
from app.models.session_model import SessionInfo

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "/",
    summary="Get all sessions for the current user",
    response_model=List[SessionInfo],
)
async def get_user_sessions(user: dict = Depends(get_current_user)):
    """
    Retrieves a list of all chat sessions associated with the user's token.
    """

    token = user["token"]
    tier = user["tier"]
    is_locked = user.get("is_locked", False)

    # 🚫 Lock check: Prevent expired paid users from fetching sessions
    if is_locked:
        raise HTTPException(
            status_code=402,
            detail="Your subscription has expired. Renew to regain access to your saved sessions."
        )

    try:
        session_ids = cache_service.smembers(f"user:{token}:sessions")

        if not session_ids:
            return []

        sessions_list = []

        # Fetch each session info
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

        # Sort newest first
        sessions_list.sort(key=lambda s: s.created_at, reverse=True)
        return sessions_list

    except Exception as e:
        print(f"[ERROR] Fetching sessions for user {token}: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve user sessions.")

@router.delete(
    "/{session_id}",
    summary = "Delete a specific user session",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user_session(session_id: str, user: dict = Depends(get_current_user)):
    """
    Deletes a specific chat session for the authenticated user.
    """
    token = user["token"]
    user_sessions_key = f"user:{token}:sessions"

    # 1. Secuity Check: Verify the user actually owns this session
    if not cache_service.client.sismember(user_sessions_key, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this session."
        )
        try:
            success = cache_service.remove_session_for_user(
                guest_token=token,
                session_id=session_id
            )
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to delete session"
                )
        except Exception as e:
            print(f"[ERROR] Deleting session {session_id} for user {token}: {e}")
            raise HTTPException(status_code=500, detail="An error occured during session deletion.")

        # A 204 response does not have a body, so we return None
        return None
