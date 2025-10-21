from datetime import datetime
from config import SUBSCRIPTION_PLANS
from app.services.db import cache_service

def activate_subscription(user_id: str, plan_name: str):
    """
    Activates or renews a user's subscription based on their selected plan.
    """
    user_key = f"user_meta: {user_id}"

    duration = SUBSCRIPTION_PLANS.get(plan_name)
    if duration is None:
        # lifetime plan - no expiry
        expiry_date = None
    else:
        expiry_date = (datetime.utcnow() + duration).isoformat()

    cache_service.hset(
        user_key, mapping={
            "is_paid": "true",
            "plan_name": plan_name,
            "expiry_date": expiry_date or "none"
        }
    )

    return {
        "status": "success",
        "plan": plan_name,
        "expiry_date": expiry_date
    }
        
