"""
Demo Endpoint Module.

This module defines a placeholder `/demo` endpoint, intended for testing
and demonstration purposes. It currently returns a static response but can
be extended later with forms, interactive demos, or sample data pipelines.
"""

from fastapi import APIRouter

# Initialize router with prefix and tag
router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/", summary="Demo Form", response_description="Placeholder response for demo route")
async def demo_form() -> dict[str, str]:
    """
    Demo form endpoint.

    **Current Behavior:**
    - NOT IMPLEMENTED. Returns a static placeholder message.
    """
    return {"message": "Demo route not implemented yet"}
