from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.db import cache_service # <-- No longer import REDIS_CLIENT
from app.security import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

class MergeRequest(BaseModel):
    guest_token: str

@router.post("/merge-guest-session")
async def merge_guest_session(
    merge_request: MergeRequest,
    user: dict = Depends(get_current_user)
):
    """
    Merges a guest user's data into the currently authenticated user's account
    by calling the centralized CacheService merge method.
    """
    if user["is_guest"]:
        raise HTTPException(
            status_code=400,
            detail="A guest user cannot be the destination for a merge."
        )

    user_id = user["user_id"]
    guest_token = merge_request.guest_token

    print(f"Merging guest '{guest_token}' into user '{user_id}'")

    try:
        # --- THE FIX ---
        # All complex logic is now in the CacheService.
        success = await cache_service.merge_guest_data(guest_token, user_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Merge operation failed in database.")

        return {"status": "success", "message": "Guest session successfully merged."}
    
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"Redis merge failed: {e}")

