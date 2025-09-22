"""
Parser Endpoint Module.

This module defines the `/parser` endpoint for handling text extraction.
It is currently a stub and will later integrate AI/ML models to process
user input and return structured results.
"""

from fastapi import APIRouter


# Initialize router with prefix and tag
router = APIRouter(
    prefix="/parser",
    tags=['parser']
)

@router.post("/extract", summary="Extract Text", response_description="Parsed text output")
async def extract_text() -> dict[str, str]:
    """
    Extract text from a given input.

    **Current Behavior:**
    - NOT IMPLEMENTED YET. Returns a static placeholder message.
    """
    return {"message": "Text extraction not yet implemented"}
