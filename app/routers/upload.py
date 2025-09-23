#!/usr/bin/env python3
"""
Upload Endpoint

Accepts a document upload, extracts text, and generates
AI-powered study materials (summary + quiz).
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from app.models.parser import parse_document
from app.services.genius import generate_content
from config import settings

router = APIRouter(prefix="/upload", tags=["upload"])

@router.post(
    "/",
    summary="Upload a document and generate study pack",
    response_description="AI-generated summary and quiz."
)
async def upload_document(file: UploadFile = File(...)) -> dict[str, str]:
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

    # Generate AI content
    summary_prompt = f"Generate a concise, easy-to-understand summary of the following text:\n\n{extracted_text}"
    quiz_prompt = f"Based on the following text, create a 5-question multiple-choice quiz. Provide an answer key at the end.\n\nTEXT:\n{extracted_text}"

    summary = generate_content(summary_prompt)
    quiz = generate_content(quiz_prompt)

    return {
        "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
        "summary": summary,
        "quiz": quiz
    }
