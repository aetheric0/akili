#!/usr/bin/env python3
"""
Upload Endpoint

Accepts a document upload, extracts text, and generates
AI-powered study materials (summary + quiz).
"""

import uuid
import json
from datetime import datetime, timedelta
from fastapi import Depends, APIRouter, File, UploadFile, HTTPException, status

from app.models.parser import parse_document
from app.models.chat_models import UploadResponse, ChatRequest, ChatResponse
from app.services.genius import genius_service
from app.security import (
    get_current_user,
    enforce_usage_limit,
    enforce_active_session_limit,
)
from app.services.db import cache_service
from config import settings

router = APIRouter(prefix="/upload", tags=["upload"])


# =====================================================
# Upload Document Endpoint
# =====================================================
@router.post(
    "/document",
    summary="Upload a document and generate a chat session",
    dependencies=[Depends(enforce_usage_limit("upload_doc"))],
    response_description="Summary, Quiz, and a chat session ID",
    response_model=UploadResponse,
)
async def upload_document_and_start_chat(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """
    Uploads a PDF/Word document, extracts its text, and generates
    an AI-powered summary and quiz using Gemini.
    """

    # ✅ 0. User context
    user_id = user["user_id"]
    user_tier = user["tier"]
    plan_name = user["plan_name"]
    expiry_date = user["expiry_date"]
    is_active = user["is_active"]
    is_locked = user["is_locked"]
    is_paid = user_tier == "paid" and is_active

    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your subscription has expired. Renew to create new study sessions.",
        )

    # ✅ 1. Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max allowed size: {settings.MAX_FILE_SIZE // (1024*1024)} MB",
        )

    # ✅ 2. Enforce active session limit (for free or expired users)
    await enforce_active_session_limit(user_id, user_tier)

    # ✅ 3. Parse document
    try:
        extracted_text = parse_document(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ✅ 4. Create a new chat session
    session_id = str(uuid.uuid4())
    ai_response = await genius_service.get_chat_response(
        session_id=session_id,
        message=extracted_text,
    )

    # ✅ 5. Initialize session data
    session_data = {
        "document_name": file.filename,
        "created_at": datetime.utcnow().isoformat(),
        "history": [{"role": "model", "text": ai_response}],
        "owner": user_id,
        "mode": "study",
        "tier": user_tier,
        "plan_name": plan_name,
        "expiry_date": expiry_date,
    }

    cache_service.add_session_for_user(user_id, session_id, session_data, tier=user_tier)

    # ✅ 6. Persistence policy based on user plan
    session_key = f"session:{session_id}"
    if is_paid:
        cache_service.persist(session_key)
    else:
        cache_service.expire(session_key, int(timedelta(days=7).total_seconds()))

    cache_service.sadd(f"user:{user_id}:sessions", session_id)
    active_sessions = len(cache_service.list_user_sessions(user_id))

    # ✅ 7. Return API response
    return {
        "session_id": session_id,
        "document_name": file.filename,
        "created_at": session_data["created_at"],
        "mode": "study",
        "response": ai_response,
        "tier": user_tier,
        "plan_name": plan_name,
        "expiry_date": expiry_date,
        "active_sessions": active_sessions,
    }


# =====================================================
# Chat Endpoint (Follow-up)
# =====================================================
@router.post(
    "/chat",
    summary="Send a follow-up message to an active AI chatbot session",
    response_model=ChatResponse,
)
async def send_user_message(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """
    Sends a follow-up message to an existing or new chat session.
    """

    try:
        # ✅ 1. Create new chat if no session_id provided
        if not request.session_id:
            await enforce_active_session_limit(user["user_id"], user["tier"])
            request.session_id = str(uuid.uuid4())

        session_key = f"session:{request.session_id}"
        session_data = cache_service.get(session_key) or {}

        if isinstance(session_data, str):
            try:
                session_data = json.loads(session_data)
            except Exception:
                session_data = {}

        session_data = session_data or {"mode": "chat", "history": []}
        is_new_chat = not session_data.get("history")

        # ✅ 2. Get AI response
        follow_up_response = await genius_service.get_chat_response(
            session_id=request.session_id,
            message=request.message,
        )

        # ✅ 3. Optional: Title generation for brand-new chats
        if is_new_chat:
            title = await genius_service.generate_session_title(
                user_message=request.message,
                ai_response=follow_up_response,
            )
            session_data["document_name"] = title
            cache_service.hset(session_key, {"document_name": title})

        return ChatResponse(
            session_id=request.session_id,
            response=follow_up_response,
        )

    except Exception as e:
        print(f"[ERROR] Follow-up chat failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get a response from the chat session.",
        )
