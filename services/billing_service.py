import os
from datetime import UTC, datetime
from typing import Any

try:
    import stripe
except Exception:  # pragma: no cover - dependency may be absent before install
    stripe = None

from database.db import (
    PaymentRecord,
    add_assessment_credits,
    get_latest_payment_for_user,
    get_user_profile,
    get_user_profile_by_id,
    get_user_profile_by_stripe_customer_id,
    get_user_profile_by_stripe_subscription_id,
    save_payment_record,
    set_stripe_customer_details,
    set_subscription_plan,
)


PRO_MONTHLY_AMOUNT = 1900
ASSESSMENT_CREDIT_AMOUNT = 499
DEFAULT_CURRENCY = "usd"


def _stripe_available() -> bool:
    return stripe is not None


def _secret_key() -> str:
    return os.getenv("STRIPE_SECRET_KEY", "").strip()


def _publishable_key() -> str:
    return (
        os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("STRIPE_PUBLIC_KEY", "").strip()
    )


def _webhook_secret() -> str:
    return os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()


def _app_base_url() -> str:
    for key in ("APP_BASE_URL", "RENDER_EXTERNAL_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return value.rstrip("/")
    return "http://127.0.0.1:8501"


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


def _from_unix(timestamp: Any) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp), tz=UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    except Exception:
        return ""


def payments_configured() -> bool:
    return bool(_secret_key() and _publishable_key() and _stripe_available())


def webhooks_configured() -> bool:
    return payments_configured() and bool(_webhook_secret())


def _configure_stripe() -> None:
    if not stripe:
        raise RuntimeError("The Stripe SDK is not installed.")
    stripe.api_key = _secret_key()


def _success_url(view: str = "app") -> str:
    return f"{_app_base_url()}/?view={view}&checkout=success"


def _cancel_url(view: str = "pro") -> str:
    return f"{_app_base_url()}/?view={view}&checkout=canceled"


def _ensure_user(user_id: int) -> dict:
    user = get_user_profile_by_id(user_id)
    if not user:
        raise ValueError("User not found.")
    return user


def _get_or_create_customer(user: dict) -> str:
    existing = (user.get("stripe_customer_id") or "").strip()
    if existing:
        return existing
    customer = stripe.Customer.create(
        email=user.get("email", ""),
        name=user.get("full_name", "") or user.get("email", ""),
        metadata={"user_id": str(user.get("id", 0)), "user_email": user.get("email", "")},
    )
    customer_id = customer.get("id", "")
    if customer_id:
        set_stripe_customer_details(user.get("email", ""), stripe_customer_id=customer_id)
    return customer_id


def create_pro_checkout_session(user_id: int) -> dict:
    if not payments_configured():
        return {"ok": False, "message": "Stripe test mode is not configured yet.", "checkout_url": ""}
    try:
        _configure_stripe()
        user = _ensure_user(user_id)
        customer_id = _get_or_create_customer(user)
        session = stripe.checkout.Session.create(
            mode="subscription",
            success_url=_success_url("app"),
            cancel_url=_cancel_url("pro"),
            customer=customer_id,
            client_reference_id=str(user_id),
            customer_update={"name": "auto"},
            metadata={
                "user_id": str(user_id),
                "user_email": user.get("email", ""),
                "product_type": "pro_monthly",
            },
            subscription_data={
                "metadata": {
                    "user_id": str(user_id),
                    "user_email": user.get("email", ""),
                    "product_type": "pro_monthly",
                }
            },
            line_items=[
                {
                    "price_data": {
                        "currency": DEFAULT_CURRENCY,
                        "unit_amount": PRO_MONTHLY_AMOUNT,
                        "recurring": {"interval": "month"},
                        "product_data": {
                            "name": "Career Match Pro",
                            "description": "Unlimited assessments, resume optimization, interview prep, cover letters, and exports.",
                        },
                    },
                    "quantity": 1,
                }
            ],
        )
        return {
            "ok": True,
            "message": "Secure Stripe Checkout is ready.",
            "checkout_url": session.get("url", ""),
            "session_id": session.get("id", ""),
            "product_type": "pro_monthly",
        }
    except Exception as exc:
        return {"ok": False, "message": f"Unable to start Stripe Checkout: {exc}", "checkout_url": ""}


def create_credit_checkout_session(user_id: int) -> dict:
    if not payments_configured():
        return {"ok": False, "message": "Stripe test mode is not configured yet.", "checkout_url": ""}
    try:
        _configure_stripe()
        user = _ensure_user(user_id)
        customer_id = _get_or_create_customer(user)
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=_success_url("app"),
            cancel_url=_cancel_url("pro"),
            customer=customer_id,
            client_reference_id=str(user_id),
            metadata={
                "user_id": str(user_id),
                "user_email": user.get("email", ""),
                "product_type": "one_time_assessment",
            },
            line_items=[
                {
                    "price_data": {
                        "currency": DEFAULT_CURRENCY,
                        "unit_amount": ASSESSMENT_CREDIT_AMOUNT,
                        "product_data": {
                            "name": "Career Match Assessment Credit",
                            "description": "One additional Career Match assessment credit. Credits do not expire.",
                        },
                    },
                    "quantity": 1,
                }
            ],
        )
        return {
            "ok": True,
            "message": "Secure Stripe Checkout is ready.",
            "checkout_url": session.get("url", ""),
            "session_id": session.get("id", ""),
            "product_type": "one_time_assessment",
        }
    except Exception as exc:
        return {"ok": False, "message": f"Unable to start Stripe Checkout: {exc}", "checkout_url": ""}


def create_billing_portal_session(user_email: str) -> dict:
    if not payments_configured():
        return {"ok": False, "message": "Stripe test mode is not configured yet.", "portal_url": ""}
    user = get_user_profile(user_email) or {}
    customer_id = (user.get("stripe_customer_id") or "").strip()
    if not customer_id:
        return {"ok": False, "message": "No Stripe customer is attached to this account yet.", "portal_url": ""}
    try:
        _configure_stripe()
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{_app_base_url()}/?view=app",
        )
        return {"ok": True, "message": "Billing portal ready.", "portal_url": session.get("url", "")}
    except Exception as exc:
        return {"ok": False, "message": f"Unable to open the billing portal: {exc}", "portal_url": ""}


def cancel_subscription(user_email: str) -> dict:
    if not payments_configured():
        return {"ok": False, "message": "Stripe test mode is not configured yet."}
    user = get_user_profile(user_email) or {}
    subscription_id = (user.get("stripe_subscription_id") or "").strip()
    if not subscription_id:
        return {"ok": False, "message": "No active Stripe subscription was found for this account."}
    try:
        _configure_stripe()
        subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        period_end = _from_unix(subscription.get("current_period_end"))
        set_subscription_plan(
            user_email,
            subscription_status="active",
            subscription_plan="pro",
            subscription_start=_from_unix(subscription.get("current_period_start")),
            subscription_end=period_end,
        )
        return {
            "ok": True,
            "message": "Your subscription will cancel at the end of the current billing period.",
            "renewal_date": period_end,
        }
    except Exception as exc:
        return {"ok": False, "message": f"Unable to cancel the subscription: {exc}"}


def _save_payment_once(user_id: int, session_id: str, payment_intent: str, amount: int, currency: str, product_type: str, status: str) -> None:
    latest = get_latest_payment_for_user(user_id)
    if latest and latest.get("stripe_session_id") == session_id and latest.get("status") == status:
        return
    save_payment_record(
        PaymentRecord(
            user_id=user_id,
            stripe_session_id=session_id,
            stripe_payment_intent=payment_intent,
            amount=int(amount or 0),
            currency=(currency or DEFAULT_CURRENCY).lower(),
            product_type=product_type,
            status=status,
            created_at=_utc_now_iso(),
        )
    )


def _resolve_user_from_payload(payload: dict) -> dict | None:
    user_email = (payload.get("user_email") or payload.get("metadata", {}).get("user_email") or "").strip().lower()
    if user_email:
        user = get_user_profile(user_email)
        if user:
            return user
    customer_id = (payload.get("stripe_customer_id") or payload.get("customer") or "").strip()
    if customer_id:
        user = get_user_profile_by_stripe_customer_id(customer_id)
        if user:
            return user
    subscription_id = (payload.get("stripe_subscription_id") or payload.get("subscription") or "").strip()
    if subscription_id:
        user = get_user_profile_by_stripe_subscription_id(subscription_id)
        if user:
            return user
    user_id = payload.get("user_id") or payload.get("metadata", {}).get("user_id") or payload.get("client_reference_id")
    if user_id:
        try:
            return get_user_profile_by_id(int(user_id))
        except Exception:
            return None
    return None


def _apply_checkout_completed(payload: dict) -> dict:
    user = _resolve_user_from_payload(payload)
    if not user:
        return {"ok": False, "message": "User not found for checkout session."}
    user_email = user.get("email", "")
    user_id = int(user.get("id", 0))
    session_id = payload.get("stripe_session_id") or payload.get("id") or ""
    payment_intent = payload.get("stripe_payment_intent") or payload.get("payment_intent") or ""
    amount = int(payload.get("amount") or payload.get("amount_total") or 0)
    currency = payload.get("currency") or DEFAULT_CURRENCY
    product_type = payload.get("product_type") or payload.get("metadata", {}).get("product_type") or ""
    customer_id = payload.get("stripe_customer_id") or payload.get("customer") or ""
    subscription_id = payload.get("stripe_subscription_id") or payload.get("subscription") or ""

    if customer_id or subscription_id:
        set_stripe_customer_details(user_email, stripe_customer_id=customer_id, stripe_subscription_id=subscription_id)

    _save_payment_once(
        user_id=user_id,
        session_id=session_id,
        payment_intent=payment_intent,
        amount=amount,
        currency=currency,
        product_type=product_type,
        status="completed",
    )

    if product_type == "one_time_assessment":
        add_assessment_credits(user_email, 1)
        return {"ok": True, "message": "Assessment credit added."}

    if product_type == "pro_monthly":
        start = payload.get("subscription_start") or _from_unix(payload.get("current_period_start"))
        end = payload.get("subscription_end") or _from_unix(payload.get("current_period_end"))
        set_subscription_plan(
            user_email,
            subscription_status="active",
            subscription_plan="pro",
            subscription_start=start,
            subscription_end=end,
        )
        return {"ok": True, "message": "Pro subscription activated."}

    return {"ok": True, "message": "Checkout completed."}


def _apply_subscription_update(payload: dict, deleted: bool = False) -> dict:
    user = _resolve_user_from_payload(payload)
    if not user:
        return {"ok": False, "message": "User not found for subscription event."}
    user_email = user.get("email", "")
    customer_id = payload.get("stripe_customer_id") or payload.get("customer") or ""
    subscription_id = payload.get("stripe_subscription_id") or payload.get("id") or ""
    if customer_id or subscription_id:
        set_stripe_customer_details(user_email, stripe_customer_id=customer_id, stripe_subscription_id=subscription_id)

    if deleted:
        set_subscription_plan(
            user_email,
            subscription_status="canceled",
            subscription_plan="free",
            subscription_start="",
            subscription_end=_from_unix(payload.get("ended_at") or payload.get("current_period_end")),
        )
        return {"ok": True, "message": "Subscription canceled."}

    status = (payload.get("subscription_status") or payload.get("status") or "active").strip().lower()
    mapped_status = "active" if status in {"active", "trialing", "past_due"} else status
    mapped_plan = "pro" if mapped_status in {"active", "trialing", "past_due"} else "free"
    set_subscription_plan(
        user_email,
        subscription_status=mapped_status,
        subscription_plan=mapped_plan,
        subscription_start=_from_unix(payload.get("current_period_start")),
        subscription_end=_from_unix(payload.get("current_period_end")),
    )
    return {"ok": True, "message": "Subscription updated."}


def handle_webhook_event(event_type: str, payload: dict) -> dict:
    if event_type == "checkout.session.completed":
        return _apply_checkout_completed(payload)
    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        return _apply_subscription_update(payload, deleted=False)
    if event_type == "customer.subscription.deleted":
        return _apply_subscription_update(payload, deleted=True)
    return {"ok": False, "message": f"Unsupported webhook event: {event_type}"}


def process_stripe_event(event: dict) -> dict:
    event_type = event.get("type", "")
    payload = (event.get("data", {}) or {}).get("object", {}) or {}
    normalized_payload = {
        **payload,
        "id": payload.get("id", ""),
        "metadata": payload.get("metadata", {}) or {},
        "customer": payload.get("customer", ""),
        "subscription": payload.get("subscription", ""),
        "payment_intent": payload.get("payment_intent", ""),
        "amount_total": payload.get("amount_total", payload.get("amount", 0)),
        "currency": payload.get("currency", DEFAULT_CURRENCY),
        "status": payload.get("status", ""),
        "current_period_start": payload.get("current_period_start"),
        "current_period_end": payload.get("current_period_end"),
        "ended_at": payload.get("ended_at"),
    }
    return handle_webhook_event(event_type, normalized_payload)


def process_webhook_request(payload: bytes, signature: str) -> tuple[dict, int]:
    if not webhooks_configured():
        return {"ok": False, "message": "Stripe webhooks are not configured."}, 503
    try:
        _configure_stripe()
        event = stripe.Webhook.construct_event(payload, signature, _webhook_secret())
        result = process_stripe_event(event)
        return result, 200 if result.get("ok") else 400
    except Exception as exc:
        return {"ok": False, "message": f"Webhook verification failed: {exc}"}, 400
