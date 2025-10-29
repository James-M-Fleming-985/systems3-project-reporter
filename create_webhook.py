#!/usr/bin/env python3
"""
Create Stripe Webhook for Systems3 Project Reporter
"""
import stripe
import os
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

try:
    # Create webhook endpoint
    webhook = stripe.WebhookEndpoint.create(
        url="https://systems3-project-reporter-production.up.railway.app/api/stripe/webhook",
        enabled_events=[
            "checkout.session.completed",
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ],
        description="Project Reporter Subscriptions"
    )
    
    print("✅ Webhook created successfully!")
    print(f"   Webhook ID: {webhook.id}")
    print(f"   URL: {webhook.url}")
    print(f"\n🔑 Webhook Signing Secret:")
    print(f"   {webhook.secret}")
    print(f"\n📝 Add this to your .env file:")
    print(f"   STRIPE_WEBHOOK_SECRET={webhook.secret}")
    
except Exception as e:
    print(f"❌ Error creating webhook: {e}")
