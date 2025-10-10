"""
Security & User Context Management
----------------------------------
Handles:
- Authorization Header parsing
- Token-based user context loading
- Subscription & expiry management
"""

from datetime import datetime, timedelta
from fastapi import Header, HTTPException
from app.services.db import cache_service
from config import SUBSCRIPTION_PLANS


def extract_token(authorization: str) -> str:
    """Extract and validate the Bearer token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]
    if not token:
        raise HTTPException(status_code=401, detail="Missing guest token")

    return token


async def get_current_user(authorization: str = Header(...)) -> dict:
    """
    Returns user context:
        {
            "token": "abc123",
            "tier": "paid",
            "plan_name": "standard_monthly",
            "expiry_date": "2025-11-09T12:00:00",
            "is_active": True,
            "is_locked": False
        }
    """

    token = extract_token(authorization)
    user_key = f"token:{token}"

    user_data = cache_service.hgetall(user_key) or {}

    tier = user_data.get("tier", "free")
    plan_name = user_data.get("plan_name", "free")
    expiry_str = user_data.get("expiry_date")

    # Compute expiry if missing or outdated
    if not expiry_str:
        duration = SUBSCRIPTION_PLANS.get(plan_name, timedelta(days=7))
        expiry_date = datetime.utcnow() + (duration or timedelta(days=9999))  # Lifetime fallback
        user_data.update({
            "tier": "paid" if plan_name != "free" else "free",
            "plan_name": plan_name,
            "expiry_date": expiry_date.isoformat(),
        })
        cache_service.hset(user_key, mapping=user_data)
    else:
        expiry_date = datetime.fromisoformat(expiry_str)

    now = datetime.utcnow()
    is_active = now <= expiry_date
    is_locked = tier == "paid" and not is_active  # Lock expired paid users

    # Grace period logic (7 days)
    grace_end = expiry_date + timedelta(days=7)
    if now > grace_end:
        tier = "free"
        is_locked = False
        user_data["tier"] = "free"

    # --- GAMIFICATION LOGIC ---
    # Load gamification stats, defaulting to 0 if not present
    xp = int(user_data.get("xp", 0))
    coins = int(user_data.get("coins", 0))
    streak_days = int(user_data.get("streak_days", 0))

    user_context = {
        "token": token,
        "tier": tier,
        "plan_name": plan_name,
        "expiry_date": expiry_date.isoformat(),
        "is_active": is_active,
        "is_locked": is_locked,
        "xp": xp,
        "coins": coins,
        "streak_days": streak_days,
    }

    # Sync back any new computed values
    cache_service.hset(user_key, mapping=user_context)
    return user_context
