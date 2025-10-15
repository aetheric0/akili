from datetime import datetime, timedelta
from fastapi import Header, HTTPException
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

async def get_current_user(authorization: str = Header(...)) -> dict:
    token = extract_token(authorization)
    user_id: str
    is_guest: bool
    email: str | None = None

    if token.startswith("guest_"):
        user_id = token
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
