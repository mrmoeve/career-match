import os
from datetime import datetime, timedelta

from database.db import (
    PaymentRecord,
    add_assessment_credits,
    get_user_profile,
    save_payment_record,
    set_stripe_customer_details,
    set_subscription_plan,
)


def payments_configured() -> bool:
    required = [
        os.getenv("STRIPE_SECRET_KEY", "").strip(),
        os.getenv("STRIPE_WEBHOOK_SECRET", "").strip(),
        os.getenv("APP_BASE_URL", "").strip(),
    ]
    return all(required)


def _fake_checkout_url(path: str) -> str:
    base = os.getenv("APP_BASE_URL", "").strip() or "http://localhost:8501"
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def create_pro_checkout_session(user_id: int) -> dict:
    price_id = os.getenv("STRIPE_PRICE_PRO_MONTHLY", "").strip()
    if not payments_configured() or not price_id:
        return {
            "ok": False,
            "message": "Payments are not configured yet.",
            "checkout_url": "",
        }
    session_id = f"cs_pro_{user_id}_{int(datetime.now().timestamp())}"
    return {
        "ok": True,
        "message": "Stripe-ready Pro checkout placeholder created.",
        "checkout_url": _fake_checkout_url(f"checkout/pro/{session_id}"),
        "session_id": session_id,
        "product_type": "pro_monthly",
    }


def create_credit_checkout_session(user_id: int) -> dict:
    price_id = os.getenv("STRIPE_PRICE_ONE_TIME_ASSESSMENT", "").strip()
    if not payments_configured() or not price_id:
        return {
            "ok": False,
            "message": "Payments are not configured yet.",
            "checkout_url": "",
        }
    session_id = f"cs_credit_{user_id}_{int(datetime.now().timestamp())}"
    return {
        "ok": True,
        "message": "Stripe-ready one-time assessment checkout placeholder created.",
        "checkout_url": _fake_checkout_url(f"checkout/credit/{session_id}"),
        "session_id": session_id,
        "product_type": "one_time_assessment",
    }


def handle_webhook_event(event_type: str, payload: dict) -> dict:
    user_email = (payload.get("user_email") or "").strip().lower()
    user = get_user_profile(user_email) if user_email else None
    if not user:
        return {"ok": False, "message": "User not found for webhook event."}

    user_id = int(user.get("id", 0))
    session_id = payload.get("stripe_session_id", "")
    payment_intent = payload.get("stripe_payment_intent", "")
    amount = int(payload.get("amount", 0))
    currency = payload.get("currency", "usd")
    product_type = payload.get("product_type", "")
    status = payload.get("status", event_type)

    if event_type == "checkout.session.completed":
        save_payment_record(
            PaymentRecord(
                user_id=user_id,
                stripe_session_id=session_id,
                stripe_payment_intent=payment_intent,
                amount=amount,
                currency=currency,
                product_type=product_type,
                status=status,
                created_at=datetime.now().isoformat(timespec="seconds"),
            )
        )
        if product_type == "one_time_assessment":
            add_assessment_credits(user_email, 1)
        elif product_type == "pro_monthly":
            set_subscription_plan(
                user_email,
                subscription_status="active",
                subscription_plan="pro",
                subscription_start=datetime.now().isoformat(timespec="seconds"),
                subscription_end=(datetime.now() + timedelta(days=30)).isoformat(timespec="seconds"),
            )
            set_stripe_customer_details(
                user_email,
                stripe_customer_id=payload.get("stripe_customer_id", ""),
                stripe_subscription_id=payload.get("stripe_subscription_id", ""),
            )
        return {"ok": True, "message": "Webhook processed."}

    if event_type in {"invoice.paid", "customer.subscription.updated"}:
        set_subscription_plan(
            user_email,
            subscription_status="active",
            subscription_plan="pro",
            subscription_start=payload.get("subscription_start", ""),
            subscription_end=payload.get("subscription_end", ""),
        )
        return {"ok": True, "message": "Subscription refreshed."}

    if event_type in {"invoice.payment_failed", "customer.subscription.deleted"}:
        set_subscription_plan(
            user_email,
            subscription_status="canceled",
            subscription_plan="free",
            subscription_start="",
            subscription_end="",
        )
        return {"ok": True, "message": "Subscription marked inactive."}

    return {"ok": False, "message": "Unsupported webhook event."}
