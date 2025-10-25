"""
Sessions Endpoint
-----------------
Handles retrieval of user chat sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import uuid4
from datetime import datetime
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
        session_ids = await cache_service.list_user_sessions(user_id)
        if not session_ids:
            return []

        sessions_list = []
        for session_id in session_ids:
            session_data = await cache_service.get(f"session:{session_id}")
            if not session_data:
                continue

            # Handle Redis string value
            if isinstance(session_data, str):
                try:
                    session_data = json.loads(session_data)
                except json.JSONDecodeError:
                    continue

            sessions_list.append(
                SessionInfo(
                    id=session_id,
                    document_name=session_data.get("document_name", "Unknown Document"),
                    created_at=session_data.get("created_at", ""),
                    mode=session_data.get("mode", "chat"),
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

    # ✅ Security check
    if session_id not in await cache_service.list_user_sessions(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this session."
        )

    try:
        session_data = await cache_service.get(f"session:{session_id}")
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found.")

        if isinstance(session_data, str):
            try:
                session_data = json.loads(session_data)
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Corrupted session data.")

        history_raw = session_data.get("history", "[]")
        history_list = (
            json.loads(history_raw)
            if isinstance(history_raw, str)
            else history_raw
        )

        return SessionDetail(
            id=session_id,
            document_name=session_data.get("document_name", "Untitled"),
            created_at=session_data.get("created_at", ""),
            mode=session_data.get("mode", ""),
            history=history_list,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Fetching details for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve session details.")


@router.post(
    "/new-chat",
    summary="Create a new, empty 'chat' session",
    response_model=SessionInfo,
)
async def create_new_chat_session(user: dict = Depends(get_current_user)):
    """
    Creates a new chat session with default parameters.
    """
    user_id = user["user_id"]
    session_id = str(uuid4())

    session_data = {
        "document_name": "New Conversation",
        "created_at": datetime.utcnow().isoformat(),
        "history": "[]",
        "owner": user_id,
        "mode": "chat",
        "tier": user["tier"],
        "plan_name": user["plan_name"],
    }

    try:
        await cache_service.add_session_for_user(user_id, session_id, session_data, tier=user["tier"])

        return SessionInfo(
            id=session_id,
            document_name=session_data["document_name"],
            created_at=session_data["created_at"],
            mode=session_data["mode"],
        )
    except Exception as e:
        print(f"[ERROR] Creating new chat session for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not create new chat session.")


@router.delete(
    "/{session_id}",
    summary="Delete a specific user session",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user_session(session_id: str, user: dict = Depends(get_current_user)):
    """
    Deletes a specific chat session for the authenticated user.
    """
    user_id = user["user_id"]
    user_sessions_key = f"user:{user_id}:sessions"

    # ✅ Security Check: Verify ownership before attempting deletion
    if not await cache_service.client.sismember(user_sessions_key, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this session."
        )

    try:
        success = await cache_service.remove_session_for_user(
            user_id=user_id,
            session_id=session_id
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete session.")
    except Exception as e:
        print(f"[ERROR] Deleting session {session_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during session deletion.")

    # A 204 response has no body
    return None
