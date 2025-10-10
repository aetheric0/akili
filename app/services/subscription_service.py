from datetime import datetime
from app.config.plans import SUBSCRIPTION_PLANS
from app.services import cache_service

def activate_subscription(guest_token: str, plan_name: str):
    """
    Activates or renews a user's subscription based on their selected plan.
    """
    user_key = f"user_meta: {guest_token}"

    duration = SUBSCRIPTION_PLANS.get(plan_name)
    if duration is None:
        # lifetime plan - no expiry
        expiry_date = None
    else:
        expiry_date = (datetime.utcnow() + duration).isoformat()

    cache_service.hset(
        user_key, mapping={
            "is_paid": "true"
            "plan_name": plan_name,
            "expiry_date": expiry_date or "none"
        }
    )

    return {
        "status": "success",
        "plan": plan_name,
        "expiry_date": expiry_date
    }
        
