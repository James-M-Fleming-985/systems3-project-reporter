# Stripe Setup Guide

## ✅ One Stripe Account for Multiple Apps

You can use **the same Stripe account** for all your applications! Stripe handles this cleanly:

### How It Works
- **One Stripe Account** → Multiple products/prices for different apps
- **Same API Keys** → Used across all your applications
- **Metadata Tags** → Distinguish customers/subscriptions by app

### Your Current Setup
```
Your Stripe Account
├── feedback-collector-mvp (existing)
│   └── Products: Feedback Pro, etc.
└── systems3-project-reporter (new)
    ├── Product: "Starter Plan - Project Reporter"
    ├── Product: "Professional Plan - Project Reporter"
    └── Product: "Enterprise Plan - Project Reporter"
```

## 🔧 Environment Variables

Add these to your Railway deployment:

```bash
# Stripe API Keys (same for all apps)
STRIPE_SECRET_KEY=sk_test_... (or sk_live_... for production)
STRIPE_PUBLISHABLE_KEY=pk_test_... (or pk_live_... for production)
STRIPE_WEBHOOK_SECRET=whsec_... (get from Stripe Dashboard)

# Stripe Price IDs (unique to this app)
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PROFESSIONAL=price_...
STRIPE_PRICE_ENTERPRISE=price_...

# Admin Secret (for developer upgrades)
ADMIN_SECRET=your_secure_random_string_here
```

## 📦 Creating Products in Stripe

### Option 1: Use the Setup Script (Recommended)

```bash
cd /workspaces/control_tower/systems3-project-reporter
python3 setup_stripe.py
```

This will:
1. Create 3 products in Stripe (Starter, Professional, Enterprise)
2. Create monthly recurring prices for each
3. Output the `.env` configuration you need

### Option 2: Manual Setup in Stripe Dashboard

1. Go to https://dashboard.stripe.com/products
2. Click "Add product"
3. For each tier:
   - **Starter**: $19.99/month
     - Name: "Starter Plan - Systems³ Project Reporter"
     - Description: "5 projects/month, 25MB files"
     
   - **Professional**: $49.99/month
     - Name: "Professional Plan - Systems³ Project Reporter"
     - Description: "25 projects/month, 100MB files"
     
   - **Enterprise**: $199.99/month
     - Name: "Enterprise Plan - Systems³ Project Reporter"
     - Description: "Unlimited projects, 1GB files"

4. Copy each Price ID (starts with `price_...`)

## 🔗 Webhook Setup

1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. Set URL: `https://your-app.up.railway.app/api/stripe/webhook`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Copy the Webhook Secret (starts with `whsec_...`)
6. Add to Railway environment as `STRIPE_WEBHOOK_SECRET`

## 🎯 Testing vs Production

### Test Mode (Current)
- Use test API keys: `sk_test_...` and `pk_test_...`
- Use test credit cards: 4242 4242 4242 4242
- No real money charged

### Production Mode
1. Switch to Live keys in Stripe Dashboard
2. Update Railway environment variables with `sk_live_...` and `pk_live_...`
3. Repeat webhook setup for production endpoint
4. Real payments will be processed! 💰

## 🔐 Security Best Practices

1. **Never commit API keys** - Use environment variables only
2. **Use different keys for test/production** - Keep them separate
3. **Rotate webhook secrets** - If compromised
4. **Monitor Stripe Dashboard** - For suspicious activity
5. **Set up ADMIN_SECRET** - Strong random value for production

## 📊 Managing Multiple Apps

### Distinguishing Customers
Add metadata when creating Stripe customers:

```python
stripe.Customer.create(
    email=user.email,
    metadata={
        "app_name": "systems3-project-reporter",
        "user_id": user.user_id
    }
)
```

### Viewing in Dashboard
- Filter by product name
- Use customer metadata
- Check customer email patterns

## 🚀 Current Status

- ✅ Subscription tiers defined
- ✅ Stripe integration code ready
- ✅ UI components built
- ⏳ Products need to be created in Stripe
- ⏳ Environment variables need to be set in Railway
- ⏳ Webhook endpoint needs to be configured

## Next Steps

1. Run `setup_stripe.py` to create products
2. Copy the output price IDs to Railway environment
3. Set up webhook in Stripe Dashboard
4. Test checkout flow in Railway deployment
5. Verify subscription upgrades work
6. Test webhook events (subscription updates)
