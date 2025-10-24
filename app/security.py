from datetime import datetime, timedelta
from fastapi import Header, HTTPException, Depends
from supabase import create_client, Client
from app.services.db import cache_service
from config import settings, SUBSCRIPTION_PLANS

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def extract_token(authorization: str) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.split(" ")[1]
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token

async def check_usage_limits(
    user_id: str,
    action: str,
    tier: str = "free"
):
    """
    Enforces daily/monthly usage limits for key actions.
    Resets counters automatically when the date changes.
    """

    # Map actions to Redis fields
    field_map = {
        "upload_doc": "daily_doc_uploads",
        "upload_image": "daily_image_uploads",
        "exam_analysis": "monthly_exam_analyses",
    }

    if action not in field_map:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    field = field_map[action]
    limits = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS["free"])

    if not limits:
        # lifetime or undefined tier -> no limits
        return

    # Fetch user stats from Redis
    key = f"user_stats:{user_id}"
    user_stats = cache_service.hgetall(key) or {}

    today = datetime.utcnow().date()
    last_reset = user_stats.get("last_reset_date")

    # Reset logic — happens automatically per new day/month
    if not last_reset or last_reset != today.isoformat():
        # Monthly reset if month changes
        monthly_analyses = user_stats.get("monthly_exam_analyses", 0)
        if not last_reset or last_reset[:7] != today.isoformat()[:7]:
            monthly_analyses = 0

        await cache_service.hset(key, {
            "daily_doc_uploads": 0,
            "daily_image_uploads": 0,
            "monthly_exam_analyses": monthly_analyses,
            "last_reset_date": today.isoformat(),
        })
        user_stats = await cache_service.hgetall(key)

    # Increment usage
    current_value = int(user_stats.get(field, 0)) + 1
    limit_value = limits[field]

    if current_value > limit_value:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You’ve reached your {field.replace('_', ' ')} limit for today. Please upgrade to continue.",
        )

    # Save the updated count
    cache_service.hset(key, {field: current_value})

def enforce_usage_limit(action: str):
    async def _enforcer(user: dict = Depends(get_current_user)):
        await check_usage_limits(user["user_id"], action)
    return _enforcer

async def enforce_active_session_limit(user_id: str, tier: str):
    """
    Checks how many active sessions the user currently has (chat + study)
    and enforces the per-tier max_sessions rule.
    """

    limits = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS["free"])
    max_sessions = limits.get("max_sessions", 5)

    active_sessions = len(cache_service.list_user_sessions(user_id))
    if active_sessions >= max_sessions:
        raise HTTPException(
            status_code=402,
            detail=f"Session limit reached ({max_sessions}). Delete an old session or upgrade your plan."
        )


async def get_current_user(authorization: str = Header(...)) -> dict:
    token = extract_token(authorization)
    user_id: str
    is_guest: bool
    email: str | None = None

    if token.startswith("guest_"):
        user_id = token.replace("guest_", "guest:")
        is_guest = True
    else:
        try:
            user_response = supabase.auth.get_user(token)
            user_id = user_response.user.id
            email = user_response.user.email
            is_guest = False
            if not user_id:
                raise Exception("User ID not found in Supabase token")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid Supabase token: {e}")

    user_data = cache_service.get_user_profile(user_id)

    if not user_data:
        print(f"New user detected: {user_id}. Creating default profile in Redis.")
        user_data = {
            "tier": "free", "plan_name": "free", "xp": "0", "coins": "0", "streak_days": "0"
        }
        # This is the ONLY time this function should write to the database.
        cache_service.set_user_profile(user_id, user_data)

    tier = user_data.get("tier", "free")
    plan_name = user_data.get("plan_name", "free")
    expiry_str = user_data.get("expiry_date")

    expiry_date = datetime.fromisoformat(expiry_str) if expiry_str else datetime.utcnow() + timedelta(days=9999)
    
    now = datetime.utcnow()
    is_active = now <= expiry_date
    is_locked = tier == "paid" and not is_active
    
    # We construct the context to be returned, but we no longer write it back.
    user_context = {
        "user_id": user_id, "is_guest": is_guest, "email": email,
        "tier": tier, "plan_name": plan_name, "expiry_date": expiry_date.isoformat(),
        "is_active": is_active, "is_locked": is_locked,
        "xp": int(user_data.get("xp", 0)), "coins": int(user_data.get("coins", 0)),
        "streak_days": int(user_data.get("streak_days", 0)),
    }
    
    return user_context
