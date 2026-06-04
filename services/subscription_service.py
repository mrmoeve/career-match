import os


def get_subscription_blueprint() -> dict:
    return {
        "provider": "Stripe",
        "public_key_configured": bool(
            os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
            or os.getenv("STRIPE_PUBLIC_KEY", "").strip()
        ),
        "secret_key_configured": bool(os.getenv("STRIPE_SECRET_KEY", "").strip()),
        "webhook_secret_configured": bool(os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()),
        "plans": [
            {
                "name": "Free",
                "status_key": "free",
                "price": "$0",
                "features": [
                    "1 assessment",
                    "History and exports included",
                ],
            },
            {
                "name": "Pro",
                "status_key": "pro",
                "price": "$19/month",
                "features": [
                    "Unlimited assessments",
                    "Unlimited Resume Builder and Interview Intelligence",
                    "History and exports included",
                ],
            },
        ],
        "next_steps": [
            "Use Stripe Checkout to upgrade to Pro or buy single assessment credits.",
            "Use Stripe webhooks to keep subscription status and credits in sync.",
            "Expose the billing portal for self-serve payment management when available.",
            "Keep assessment gating tied to free usage, credits, and Pro status.",
        ],
    }
