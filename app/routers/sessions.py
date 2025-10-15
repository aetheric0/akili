"""
Sessions Endpoint
-----------------
Handles retrieval of user chat sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import json

from app.security import get_current_user
from app.services.db import cache_service
from app.models.session_model import SessionInfo, SessionDetail

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

    user_id = user["user_id"]
    tier = user["tier"]
    is_locked = user.get("is_locked", False)

    # 🚫 Lock check: Prevent expired paid users from fetching sessions
    if is_locked:
        raise HTTPException(
            status_code=402,
            detail="Your subscription has expired. Renew to regain access to your saved sessions."
        )

    try:
        session_ids = cache_service.list_user_sessions(user_id)

        if not session_ids:
            return []

        sessions_list = []
        # Fetch each session info
        for session_id in session_ids:
            session_data = cache_service.get(f"session:{session_id}")
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
        print(f"[ERROR] Fetching sessions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve user sessions.")

@router.get(
    "/{session_id}",
    summary="Get full details for a single session",
    response_model=SessionDetail,
)
async def get_session_details(session_id: str, user: dict = Depends(get_current_user)):
    """
    Retrieves the full data for a specific session, including its chat history.
    """
    user_id = user["user_id"]

    # Security check: Ensure the user owns this session
    if session_id not in cache_service.list_user_sessions(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this session."
        )

    try:
        # THE FIX: Use .get() to retrieve the session as a JSON string, which is correct for your setup.
        session_data = cache_service.get(f"session:{session_id}")
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found.")
        
        # The history is stored as a JSON string within the retrieved data, so we parse it.
        history_list = json.loads(session_data.get("history", "[]"))
        
        return SessionDetail(
            id=session_id,
            document_name=session_data.get("document_name", "Untitled"),
            created_at=session_data.get("created_at", ""),
            history=history_list,
        )
    except Exception as e:
        print(f"[ERROR] Fetching details for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve session details.")


@router.delete(
    "/{session_id}",
    summary = "Delete a specific user session",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user_session(session_id: str, user: dict = Depends(get_current_user)):
    """
    Deletes a specific chat session for the authenticated user.
    """
    user_id = user["user_id"]
    user_sessions_key = f"user:{user_id}:sessions"

    # 1. Secuity Check: Verify the user actually owns this session
    if not cache_service.client.sismember(user_sessions_key, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this session."
        )
        try:
            success = cache_service.remove_session_for_user(
                user_id=user_id,
                session_id=session_id
            )
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to delete session"
                )
        except Exception as e:
            print(f"[ERROR] Deleting session {session_id} for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="An error occured during session deletion.")

        # A 204 response does not have a body, so we return None
        return None
