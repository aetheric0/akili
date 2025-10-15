from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.db import cache_service, REDIS_CLIENT
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
    """
    if user["is_guest"]:
        raise HTTPException(
        status_code=400,
        detail=(
            "[ERROR] A guest cannot merge a session:" 
            "  Cannot merge a user into themselves."
        )
    )

    user_id = user["user_id"]
    guest_token = merge_request.guest_token

    print(f"Merging '{guest_token}' into user '{user_id}'")

    # Redis Keys
    guest_stats_key = f"user_stats:{guest_token}"
    user_stats_key = f"user_stats:{user_id}"
    guest_sessions_key = f"user:{guest_token}:sessions"
    user_sessions_key = f"user:{user_id}:sessions"

    try:
        pipe = REDIS_CLIENT.pipeline()

        # 1. Merge gamification stats (XP, Coins, etc.)
        guest_stats = cache_service.hgetall(guest_stats_key)
        if guest_stats:
            user_stats = cache_service.hgetall(user_stats_key)
            
            new_xp = int(user_stats.get("xp", 0)) + int(guest_stats.get("xp", 0))
            new_coins = int(user_stats.get("coins", 0)) + int(guest_stats.get("coins", 0))
            new_tier =guest_stats.get("tier", "free")
            new_expiry = guest_stats.get("expiry_date")

            update_mapping = {"xp": new_xp, "coins": new_coins, "tier": new_tier}
            if new_expiry:
                update_mapping["expiry_date"] = new_expiry
            
            pipe.hset(user_stats_key, mapping=update_mapping)
            pipe.delete(guest_stats_key)

        # 2. Merge the set of session IDs
        guest_session_ids = cache_service.smembers(guest_sessions_key)
        if guest_session_ids:
            pipe.sadd(user_sessions_key, *guest_session_ids)
            # 3. Update the 'owner' field in each individual sessions hash
            for session_id in guest_session_ids:
                pipe.hset(f"session:{session_id}", "owner", user_id)
            pipe.delete(guest_sessions_key)

        pipe.execute()
        return {"status": "success", "message": "Guest session successfuly merged."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis merge failed: {e}")
