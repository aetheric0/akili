"""
Payment Endpoint Module.

This module defines the `/payment` endpoint for handling user payments.
Currently, it contains placeholder logic and should be extended to
integrate with a payment provider (e.g., Stripe, Paypal, Mobile Money,
 or PayStack)
"""

from datetime import datetime
from fastapi import APIRouter
from app.services.db import cache_service

# Initialize router with prefix and tag
router = APIRouter(
    prefix="/payment",
    tags=["payment"]
)

@router.post(
    "/confirm",
    summary="Confirm Payment",
    response_description="Payment confirmation response"
)
async def confirm_payment(guest_token: str, tier: str = "basic") -> dict[str, str]:
    try:
        
        """
        Confirm Payment Status of user
        """
        # Store token payment status
        cache_service.hset(f"token:{guest_token}", {
            "tier": tier,
            "paid": "true",
            "activated_at": datetime.utcnow().isoformat()
        })
        return {"status": "success", "message": f"Token {guest_token} upgraded to {tier} plan"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment confirmation failed: {e}")
