import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest

import services.billing_service as billing_service


class FakeStripeResource:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeCustomerAPI:
    @staticmethod
    def create(**kwargs):
        return FakeStripeResource(id="cus_test_local", metadata=kwargs.get("metadata", {}))


class FakeCheckoutSessionAPI:
    calls = []

    @classmethod
    def create(cls, **kwargs):
        cls.calls.append(kwargs)
        return FakeStripeResource(id="cs_test_local", url="https://checkout.stripe.test/session/cs_test_local")


class FakeCheckoutAPI:
    Session = FakeCheckoutSessionAPI


class FakeStripeModule:
    api_key = ""
    Customer = FakeCustomerAPI
    checkout = FakeCheckoutAPI


def main() -> None:
    os.environ["APP_BASE_URL"] = "https://career-match.test"
    os.environ["STRIPE_PUBLISHABLE_KEY"] = "pk_test_local"
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_local"
    os.environ["STRIPE_PRO_MONTHLY_PRICE_ID"] = "price_test_pro_monthly"

    original_stripe = billing_service.stripe
    try:
        billing_service.stripe = FakeStripeModule()

        at = AppTest.from_file("app.py")
        at.run()
        next(button for button in at.button if button.label == "Start Free Analysis").click()
        at.run()

        email = f"stripe-checkout-{uuid4().hex[:8]}@example.com"
        inputs_by_key = {item.key: item for item in at.text_input}
        inputs_by_key["register_email"].set_value(email)
        inputs_by_key["register_password"].set_value("CareerMatch123")
        inputs_by_key["register_confirm_password"].set_value("CareerMatch123")
        next(button for button in at.button if button.label == "Create Account").click()
        at.run()

        next(item for item in at.radio if item.label == "Navigation").set_value("Pro")
        at.run()
        next(button for button in at.button if button.label == "Upgrade to Career Match Pro").click()
        at.run()

        print("button_reached_backend", len(FakeCheckoutSessionAPI.calls) == 1)
        print("price_id_used", FakeCheckoutSessionAPI.calls[0]["line_items"][0]["price"])
        print("success_url", FakeCheckoutSessionAPI.calls[0]["success_url"])
        print("cancel_url", FakeCheckoutSessionAPI.calls[0]["cancel_url"])
        print("checkout_url_returned", at.session_state["pro_checkout_url"])
        print("last_checkout_exception", at.session_state["last_checkout_exception"])
    finally:
        billing_service.stripe = original_stripe


if __name__ == "__main__":
    main()
