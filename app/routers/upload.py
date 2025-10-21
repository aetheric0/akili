#!/usr/bin/env python3
"""
Upload Endpoint

Accepts a document upload, extracts text, and generates
AI-powered study materials (summary + quiz).
"""

import uuid
import json
from datetime import datetime, timedelta
from fastapi import Depends, APIRouter, File, UploadFile, HTTPException

from app.models.parser import parse_document
from app.models.chat_models import UploadResponse, ChatRequest, ChatResponse
from app.services.genius import genius_service
from app.security import get_current_user  # ✅ centralized user info
from app.services.db import cache_service
from config import settings

router = APIRouter(prefix="/upload", tags=["upload"])


# =====================================================
# Upload Endpoint
# =====================================================
@router.post(
    "/document",
    summary="Upload a document and generate a chat session",
    response_description="Summary, Quiz, and a chat session ID",
    response_model=UploadResponse
)
async def upload_document_and_start_chat(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),  # ✅ centralized user info
) -> dict[str, str]:
    """
    Uploads a PDF/Word document, extracts its text, and generates
    an AI-powered summary and quiz using Gemini.

    Rules:
    - Free users: max 5 active sessions.
    - Paid active users: unlimited sessions.
    - Expired paid users: treated as free tier until renewal.
    """

    # ✅ 0. User Context
    user_id = user["user_id"]
    user_tier = user["tier"]
    is_active = user["is_active"]
    plan_name = user["plan_name"]
    expiry_date = user["expiry_date"]
    is_locked = user.get("is_locked", False)
    is_paid = user_tier == "paid" and is_active

    if is_locked:
        raise HTTPException(
            status_code=402,
            detail="Your subscription has expired. Renew to create new study sessions.",
        )

    # ✅ 1. Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max allowed size: {settings.MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # ✅ 2. Enforce active session limit (for free & expired users)
    session_set_key = f"user:{user_id}:sessions"
    # cache_service.smembers returns a set; list_user_sessions returns list
    active_session_count = len(cache_service.list_user_sessions(user_id))

    MAX_FREE_SESSIONS = 5
    if not is_paid and active_session_count >= MAX_FREE_SESSIONS:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Free and expired users can only have up to "
                f"{MAX_FREE_SESSIONS} active sessions. "
                f"Delete an old session or upgrade to continue."
            )
        )

    # ✅ 3. Parse document
    try:
        extracted_text = parse_document(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ✅ 4. Create a new chat session (ask genius_service to process initial doc)
    session_id = str(uuid.uuid4())
    # call service; it should produce first ai response (summary+quiz) and also persist history
    initial_ai_response = await genius_service.get_chat_response(
        session_id=session_id,
        message=extracted_text,
    )

    # -------------------------
    # 5. Compose session data (preserve any history genius_service already stored)
    # -------------------------
    session_key = f"session:{session_id}"
    stored = cache_service.get(session_key)  # CacheService.get returns parsed JSON or None

    # Determine history: prefer stored history if present (list), otherwise create one.
    history = None
    if stored and isinstance(stored, dict):
        h = stored.get("history")
        if isinstance(h, list) and h:
            history = h

    if history is None:
        # If genius didn't persist history for some reason, initialize with assistant response
        # Note: keep role "model" for backward compatibility with existing code
        history = [{"role": "model", "text": initial_ai_response}]

    # Build session payload with the same keys your app expects
    session_data = {
        "document_name": file.filename,
        "created_at": datetime.utcnow().isoformat(),
        "history": history,
        "owner": user_id,
        "mode": "study",
        "tier": user_tier,
        "plan_name": plan_name,
        "expiry_date": expiry_date,
    }

    # Use CacheService.add_session_for_user which will set the session key and add to the user's set.
    # This preserves your existing public helper and ensures consistent indexing.
    cache_service.add_session_for_user(user_id, session_id, session_data, tier=user_tier)

    # ✅ 6. Apply storage policy based on user tier
    # Use the full session key when calling expire/persist (fixes earlier bug that passed id alone)
    if is_paid:
        cache_service.persist(session_key)  # persistent for active paid users
        print(f"[Redis:policy] Persistent session for paid user {user_id}")
    else:
        cache_service.expire(session_key, int(timedelta(days=7).total_seconds()))
        print(f"[Redis:policy] TTL(7 days) applied for free/expired user {user_id}")

    # ✅ 7. Track session under user's active sessions
    cache_service.sadd(session_set_key, session_id)

    # ✅ 8. Return response
    return {
        "session_id": session_id,
        "document_name": file.filename,
        "created_at": session_data["created_at"],
        "mode": "study",
        "response": initial_ai_response,
        "tier": user_tier,
        "plan_name": plan_name,
        "expiry_date": expiry_date,
        "active_sessions": active_session_count + 1,
    }


# =====================================================
# Follow-up Chat Endpoint
# =====================================================
@router.post(
    "/chat",
    summary="Send a follow-up message to an active AI chatbot chat session",
    response_model=ChatResponse,
)
async def send_user_message(request: ChatRequest):
    """Sends a follow-up message to an existing chat session."""
    try:
        if not request.session_id:
            request.session_id = str(uuid.uuid4())
        session_key = f"session:{request.session_id}"
        # Use cache_service.get which returns parsed JSON (consistent with add_session_for_user)
        session_data = cache_service.get(session_key) or {}

        if isinstance(session_data, str):
            try:
                session_data = json.loads(session_data)
            except Exception:
                session_data = {}

        session_data = session_data or {"mode": "chat", "history": []}

        # If session_data was stored as a hash somewhere else, this still yields {}
        # Determine if this is a new chat (no history yet)
        is_new_chat = session_data.get("mode") == "chat" and not session_data.get("history")

        # Ask genius service to handle message and append history (it expects session_id + message)
        follow_up_response = await genius_service.get_chat_response(
            session_id=request.session_id,
            message=request.message,
        )

        # If this was an empty chat just created, generate a session title in background
        if is_new_chat:
            title = await genius_service.generate_session_title(
                user_message=request.message,
                ai_response=follow_up_response
            )
            session_data["document_name"] = title

        return ChatResponse(
            session_id=request.session_id,
            response=follow_up_response
        )
    except Exception as e:
        print(f"[ERROR] Follow-up chat failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get a response from the chat session."
        )
