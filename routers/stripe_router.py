"""
Stripe API Routes for Systems3 Project Reporter
Handles Stripe checkout, webhooks, and subscription management
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
from typing import Dict, Any

from services.stripe_service import StripeService
from models.user import SubscriptionTier, User
from middleware.subscription import get_user_or_create_anonymous

router = APIRouter(prefix="/api/stripe", tags=["stripe"])
stripe_service = StripeService()

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    user: User = Depends(get_user_or_create_anonymous)
):
    """Create Stripe checkout session for subscription upgrade"""
    try:
        data = await request.json()
        tier_str = data.get("tier", "starter")
        customer_email = data.get("customer_email") or user.email
        
        # Validate tier
        try:
            tier = SubscriptionTier(tier_str.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid subscription tier: {tier_str}"
            )
        
        # Don't allow downgrade or same tier
        current_tiers = list(SubscriptionTier)
        current_index = current_tiers.index(user.subscription_tier)
        target_index = current_tiers.index(tier)
        
        if target_index <= current_index:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot downgrade from {user.subscription_tier.value} to {tier.value}"
            )
        
        # Create checkout session
        base_url = str(request.base_url).rstrip('/')
        success_url = f"{base_url}/subscription/success"
        cancel_url = f"{base_url}/subscription"
        
        session = stripe_service.create_checkout_session(
            tier=tier,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email
        )
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "tier": tier.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Stripe checkout error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create checkout session: {str(e)}"
        )


@router.post("/create-portal-session")
async def create_portal_session(
    request: Request,
    user: User = Depends(get_user_or_create_anonymous)
):
    """Create Stripe customer portal session"""
    try:
        data = await request.json()
        customer_id = data.get("customer_id")
        
        if not customer_id:
            raise HTTPException(
                status_code=400,
                detail="customer_id required"
            )
        
        base_url = str(request.base_url).rstrip('/')
        return_url = f"{base_url}/subscription"
        
        session = stripe_service.create_portal_session(
            customer_id=customer_id,
            return_url=return_url
        )
        
        return {"url": session.url}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create portal session: {str(e)}"
        )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Webhook secret not configured"
        )
    
    import stripe
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event["type"]
    event_data = event["data"]["object"]
    
    print(f"🔔 Stripe webhook received: {event_type}")
    
    # Handle different event types
    try:
        if event_type == "checkout.session.completed":
            await stripe_service.handle_checkout_completed(event_data)
        elif event_type == "customer.subscription.updated":
            await stripe_service.handle_subscription_updated(event_data)
        elif event_type == "customer.subscription.deleted":
            await stripe_service.handle_subscription_deleted(event_data)
        elif event_type == "invoice.payment_failed":
            await stripe_service.handle_payment_failed(event_data)
        else:
            print(f"ℹ️ Unhandled event type: {event_type}")
    except Exception as e:
        print(f"❌ Error handling webhook {event_type}: {e}")
        # Don't raise - return 200 to avoid Stripe retries
    
    return JSONResponse(content={"received": True})


@router.get("/subscription-status/{customer_id}")
async def get_subscription_status(
    customer_id: str,
    user: User = Depends(get_user_or_create_anonymous)
):
    """Get current Stripe subscription status for a customer"""
    try:
        status = await stripe_service.get_subscription_status(customer_id)
        return status
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get subscription status: {str(e)}"
        )


@router.get("/price-ids")
async def get_stripe_price_ids():
    """Get configured Stripe price IDs for each tier"""
    return {
        "starter": os.getenv("STRIPE_PRICE_ID_STARTER"),
        "professional": os.getenv("STRIPE_PRICE_ID_PROFESSIONAL"),
        "enterprise": os.getenv("STRIPE_PRICE_ID_ENTERPRISE"),
    }