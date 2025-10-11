from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import hmac
import hashlib
import json
import requests
import re

from app.security import get_current_user
from app.services import subscription_service # Use your subscription service
from app.models.payment_models import MpesaRequest
from config import settings

router = APIRouter(prefix="/payments", tags=["payments"])

# -- Helper Function --
def normalize_kenyan_phone_number(phone: str) -> str:
    """
    Sanitizes and normalizes a Kenyan phone number to the required +254... format.
    """
    # 1. Remove all characters that are not digits, then remove leading zeros if present
    sanitized_phone = re.sub(r'\D', '', phone).lstrip('0')
        
    # 2. Check the remaining number length and format correctly
    if sanitized_phone.startswith('254') and len(sanitized_phone) == 12:
        return f"+{sanitized_phone}"
    elif sanitized_phone.startswith('7') and len(sanitized_phone) == 9:
        return f"+254{sanitized_phone}"
    else:
    # If it doesn't match a valid Kenyan format after cleaning, it's invalid
        raise ValueError(f"Invalid phone number format provided: '{phone}'")


PAYSTACK_API_BASE = "https://api.paystack.co"
AMOUNTS_KES = {
    "basic_weekly": 50 * 100,
    "standard_monthly": 199 * 100,
}

@router.post("/initialize-mpesa", summary="Initialize an M-Pesa STK Push payment")
async def initialize_mpesa_payment(
    request: MpesaRequest,
    user: dict = Depends(get_current_user)
):
    """
    Initializes a Paystack M-Pesa charge (STK Push) for a user.
    """
    guest_token = user["token"]
    amount = AMOUNTS_KES.get(request.plan_name)
    if not amount:
        raise HTTPException(status_code=400, detail="Invalid plan name.")

    # --- USE THE NORMALIZED PHONE NUMBER ---
    try:
        normalized_phone = normalize_kenyan_phone_number(request.phone_number)
        print(normalized_phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    url = f"{PAYSTACK_API_BASE}/charge"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    payload = {
        "email": f"{guest_token}@akili.app",
        "amount": str(amount),
        "currency": "KES",
        "metadata": {
            "guest_token": guest_token,
            "plan_name": request.plan_name,
        },
        "mobile_money": {
            "phone": normalized_phone, # Use the corrected phone number
            "provider": "mpesa"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()["data"]
        
        # Paystack returns a reference code for the pending transaction
        # You can use this to check status later if needed
        return {
            "status": data.get("status"),
            "reference": data.get("reference"),
            "display_text": data.get("display_text")
        }

    except requests.exceptions.RequestException as e:
        error_details = "No response text."
        if e.response is not None:
            try:
                error_details = e.response.json()
            except json.JSONDecodeError:
                error_details = e.response.text
                
        print("--- PAYSTACK API REQUEST FAILED ---")
        print(error_details)
        raise HTTPException(status_code=500, detail="Could not initialize M-Pesa payment.")
        

@router.post("/webhook", summary="Handle Paystack webhook events")
async def handle_paystack_webhook(request: Request):
    """
    Listens for 'charge.success' events from Paystack and activates subscriptions.
    """
    body = await request.body()
    # 1. Verify webhook signature for security
    signature = request.headers.get("x-paystack-signature")
    hashed = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    if hashed != signature:
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event = json.loads(body)
    # 2. Process the successful charge event
    if event.get('event') == 'charge.success':
        data = event['data']
        metadata = data.get('metadata', {})
        guest_token = metadata.get('guest_token')
        plan_name = metadata.get('plan_name')

        if not guest_token or not plan_name:
            # Can't process without metadata, but return 200 so Paystack doesn't retry
            print("Webhook received with missing metadata.")
            return {"status": "ignored"}
            
        print(f"✅ Payment successful for user {guest_token}, plan {plan_name}")
        
        # 3. Call your subscription service to activate the plan
        subscription_service.activate_subscription(
            guest_token=guest_token,
            plan_name=plan_name
        )
        
    return {"status": "received"}
