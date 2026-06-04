from flask import Flask, jsonify, request

from database.db import init_db
from services.billing_service import process_webhook_request


app = Flask(__name__)


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "billing-webhooks"})


@app.post("/stripe/webhook")
def stripe_webhook():
    init_db()
    result, status_code = process_webhook_request(
        request.get_data(),
        request.headers.get("Stripe-Signature", ""),
    )
    return jsonify(result), status_code


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8601)
