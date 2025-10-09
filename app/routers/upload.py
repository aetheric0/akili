#!/usr/bin/env python3
"""
Upload Endpoint

Accepts a document upload, extracts text, and generates
AI-powered study materials (summary + quiz).
"""

import uuid
import json
from datetime import datetime
from typing import Annotated

# FastApi imports
from fastapi import Depends, APIRouter, File, UploadFile, HTTPException


# App Imports
from app.models.parser import parse_document
from app.models.chat_models import ChatRequest, ChatResponse
from app.services.genius import genius_service
from app.security import get_current_user_token
from app.services.db import cache_service

# Configuration Imports
from config import settings
from pydantic import BaseModel      # Used for chat request body

router = APIRouter(prefix="/upload", tags=["upload"])

@router.post(
    "/document",
    summary="Upload a document and generate a chat session",
    response_description="Summary, Quiz, and a chat session ID"
)
async def upload_document_and_start_chat(
        file: UploadFile = File(...),
        guest_token: str = Depends(get_current_user_token)
    ) -> dict[str, str]:
    """
    Uploads a PDF/Word document, extracts its text, and generates
    an AI-powered summary and quiz using Gemini.

    Args:
        file (UploadFile): User-uploaded document.

    Returns:
        dict[str, str]: A JSON response with extracted text, summary, and quiz.
    """
    file_bytes = await file.read()

    # Validate size
    if len(file_bytes) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max allowed size: {settings.MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # Parse document
    try:
        extracted_text = parse_document(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Generate a unique session ID
    session_id = str(uuid.uuid4())

    initial_ai_response = await genius_service.get_chat_response(
            session_id=session_id,
            message=extracted_text
        )
    

    # Store session metadata (e.g., in a Redis Hash)
    cache_service.hset(f"session:{session_id}", mapping={
        "document_name": file.filename,
        "created_at": datetime.utcnow().isoformat(),
        # Store the initial AI response here
        "history": json.dumps([{"role": "model", "text": initial_ai_response}])
    })

    # Link this session_id to the user's guest token (e.g., in a Redis Set)
    cache_service.sadd(f"user:{guest_token}", session_id)

    # Creates chat session and sends the first message (the file content)
    # The first message *is* the content/prompt. The system_context in
    # gemini.py will use this text.
    # This will call get_or_create_chat_session implicitly inside
    # get_chat_response
    # Returns the session ID and the first AI response
    return {
        "session_id": session_id,
        "response": initial_ai_response
    }

@router.post(
    "/chat",
    summary="Send a follow-up message to an active AI chatbot chat session",
    response_model=ChatResponse,
)
async def send_user_message(request: ChatRequest):
    """
    Sends a follow-up message to an existing chat session using the data
    from the ChatRequest body (session_id and message).
    """
    try:
        # Call the service using the fields from the request body
        follow_up_response = await genius_service.get_chat_response(
            session_id=request.session_id,
            message=request.message
        )

        # Return a ChatResponse object
        return ChatResponse(
            session_id=request.session_id,
            response=follow_up_response
        )
    except Exception as e:
        # ... (error handling) ...
        print("Error during follow-up chat: {}".format(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get a response from the chat session."
        )
