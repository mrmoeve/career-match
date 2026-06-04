import os


def get_subscription_blueprint() -> dict:
    return {
        "provider": "Stripe",
        "public_key_configured": bool(os.getenv("STRIPE_PUBLIC_KEY", "").strip()),
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
            "Create Stripe products and prices for Free and Pro plans.",
            "Expose checkout and customer portal links from this profile page.",
            "Handle Stripe webhook events to update subscription_status in SQLite.",
            "Gate premium usage by subscription_status once billing goes live.",
        ],
    }
