"""
Stripe Service for Systems3 Project Reporter
Business logic for handling Stripe payments and project-based subscriptions
"""
import stripe
import os
from typing import Dict, Any, Optional
from datetime import datetime

from models.user import SubscriptionTier, SUBSCRIPTION_TIERS


class StripeService:
    """Service for handling Stripe payment operations"""
    
    def __init__(self):
        self.api_key = os.getenv("STRIPE_SECRET_KEY")
        if not self.api_key or self.api_key.startswith("sk_test_51QGjZdGt9vZpMqGgabcdef"):
            print("⚠️  WARNING: Using placeholder Stripe API key. Please set STRIPE_SECRET_KEY in .env")
            print("   Get your keys from: https://dashboard.stripe.com/test/apikeys")
        stripe.api_key = self.api_key
        
        # Price IDs for each tier (to be configured via environment or setup script)
        self.price_ids = {
            SubscriptionTier.STARTER: os.getenv("STRIPE_PRICE_ID_STARTER"),
            SubscriptionTier.PROFESSIONAL: os.getenv("STRIPE_PRICE_ID_PROFESSIONAL"),
            SubscriptionTier.ENTERPRISE: os.getenv("STRIPE_PRICE_ID_ENTERPRISE"),
        }
    
    def create_checkout_session(
        self,
        tier: SubscriptionTier,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None
    ) -> stripe.checkout.Session:
        """Create a Stripe Checkout session for project subscription"""
        price_id = self.price_ids.get(tier)
        if not price_id:
            raise ValueError(f"Price ID not configured for tier: {tier}")
        
        tier_info = SUBSCRIPTION_TIERS[tier]
        
        session_params = {
            "mode": "subscription",
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": cancel_url,
            "allow_promotion_codes": True,
            "billing_address_collection": "auto",
            "metadata": {
                "subscription_tier": tier.value,
                "max_projects_monthly": str(tier_info.max_projects_per_month),
                "max_total_projects": str(tier_info.max_total_projects)
            }
        }
        
        if customer_email:
            session_params["customer_email"] = customer_email
        
        return stripe.checkout.Session.create(**session_params)
    
    def create_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> stripe.billing_portal.Session:
        """Create a Customer Portal session for managing subscriptions"""
        return stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
    
    async def handle_checkout_completed(self, session: Dict[str, Any]) -> None:
        """Handle successful checkout - user subscribed to project plan"""
        customer_id = session.get("customer")
        customer_email = session.get("customer_email") or \
                        session.get("customer_details", {}).get("email")
        subscription_id = session.get("subscription")
        
        # Get tier from metadata
        metadata = session.get("metadata", {})
        tier_value = metadata.get("subscription_tier", "starter")
        tier = SubscriptionTier(tier_value)
        tier_info = SUBSCRIPTION_TIERS[tier]
        
        print(f"✅ New {tier.value} subscription: {customer_email}")
        print(f"   Customer ID: {customer_id}")
        print(f"   Subscription ID: {subscription_id}")
        print(f"   Project Limits: {tier_info.max_projects_per_month}/month, {tier_info.max_total_projects} total")
        
        # Track analytics event
        self._track_analytics('subscription_completed', {
            'customer_id': customer_id,
            'customer_email': customer_email,
            'subscription_id': subscription_id,
            'tier': tier.value,
            'amount': tier_info.price_monthly_usd,
            'currency': 'USD',
            'max_projects_monthly': tier_info.max_projects_per_month,
            'max_total_projects': tier_info.max_total_projects
        })
        
        # TODO: Update your database with subscription info
        # TODO: Send welcome email with tier details
        # TODO: Grant access to tier features
    
    async def handle_subscription_updated(
        self, subscription: Dict[str, Any]
    ) -> None:
        """Handle subscription update (renewal, upgrade, etc.)"""
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")
        status = subscription.get("status")
        
        print(f"🔄 Subscription updated: {subscription_id}")
        print(f"   Customer: {customer_id}")
        print(f"   Status: {status}")
        
        # TODO: Update database with new status/tier
    
    async def handle_subscription_deleted(
        self, subscription: Dict[str, Any]
    ) -> None:
        """Handle subscription cancellation"""
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")
        
        print(f"❌ Subscription cancelled: {subscription_id}")
        print(f"   Customer: {customer_id}")
        
        # Track analytics event
        self._track_analytics('subscription_cancelled', {
            'customer_id': customer_id,
            'subscription_id': subscription_id
        })
        
        # TODO: Revert to free tier in database
        # TODO: Send cancellation confirmation email
    
    async def handle_payment_failed(self, invoice: Dict[str, Any]) -> None:
        """Handle failed payment"""
        customer_id = invoice.get("customer")
        
        print(f"⚠️ Payment failed for customer: {customer_id}")
        
        # TODO: Send payment failed email
        # TODO: Consider grace period before downgrading
    
    async def get_subscription_status(
        self, customer_id: str
    ) -> Dict[str, Any]:
        """Get current subscription status for a customer"""
        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status="all",
                limit=1
            )
            
            if not subscriptions.data:
                return {"status": "none", "tier": "free"}
            
            sub = subscriptions.data[0]
            
            # Try to determine tier from price ID
            tier = "free"
            if sub.items.data:
                price_id = sub.items.data[0].price.id
                for t, pid in self.price_ids.items():
                    if pid == price_id:
                        tier = t.value
                        break
            
            return {
                "status": sub.status,
                "tier": tier,
                "current_period_end": sub.current_period_end,
                "cancel_at_period_end": sub.cancel_at_period_end,
                "price_id": sub.items.data[0].price.id if sub.items.data else None
            }
        except Exception as e:
            print(f"Error fetching subscription: {e}")
            return {"status": "error", "tier": "free", "message": str(e)}
    
    def _track_analytics(self, event: str, properties: Dict[str, Any]) -> None:
        """
        Track analytics events for project subscription business
        """
        print(f"📊 Analytics Event: {event}")
        print(f"   Properties: {properties}")
        
        # TODO: Send to analytics platforms
        # TODO: Track project usage patterns
        # TODO: Monitor conversion funnels by tier