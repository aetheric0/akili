"""
Parser Endpoint Module.

Provides routes for extracting text from uploaded PDF and Word documents.
Delegates parsing logic to the parser module (pdfminer + Tika).
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from app.models.parser import parse_document
from config import settings
import os


# Initialize router with prefix and tag
router = APIRouter(
    prefix="/parser",
    tags=['parser']
)

@router.post(
    "/extract",
    summary="Extract text from a document",
    response_description="The extracted text content from the uploaded file."
)
async def extract_text(file: UploadFile = File(...)) -> dict[str, str]:
    """
    Extract text from a given input.

    **Current Behavior:**
    - NOT IMPLEMENTED YET. Returns a static placeholder message.
    """
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too larrge. Maximum allowed size is 5MB."
        )
    try:
        extracted_text = parse_document(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    response = {"extracted_text": extracted_text}

    return response
