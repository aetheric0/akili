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
from app.security import get_current_user  # ✅ New dependency
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
    token = user["token"]
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
    session_set_key = f"user:{token}:sessions"
    session_ids = cache_service.smembers(session_set_key)
    active_session_count = len(session_ids or [])

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

    # ✅ 4. Create a new chat session
    session_id = str(uuid.uuid4())
    initial_ai_response = await genius_service.get_chat_response(
        session_id=session_id,
        message=extracted_text
    )

    # ✅ 5. Store session metadata
    session_key = f"session:{session_id}"
    cache_service.hset(
        session_key,
        mapping={
            "document_name": file.filename,
            "created_at": datetime.utcnow().isoformat(),
            "history": json.dumps(
                [{"role": "model", "text": initial_ai_response}]
            ),
            "owner": token,
            "tier": user_tier,
            "plan_name": plan_name,
            "expiry_date": expiry_date,
        },
    )

    # ✅ 6. Apply storage policy based on user tier
    if is_paid:
        cache_service.persist(session_key)  # persistent for active paid users
        print(f"[Redis:policy] Persistent session for paid user {token}")
    else:
        cache_service.expire(session_key, int(timedelta(days=7).total_seconds()))
        print(f"[Redis:policy] TTL(7 days) applied for free/expired user {token}")

    # ✅ 7. Track session under user's active sessions
    cache_service.sadd(session_set_key, session_id)

    # ✅ 8. Return response
    return {
        "session_id": session_id,
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
        follow_up_response = await genius_service.get_chat_response(
            session_id=request.session_id,
            message=request.message
        )
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
