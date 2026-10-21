import stripe
from fastapi import HTTPException
from sqlalchemy import select
from .billing import journal
from .config import settings
from .models import Topup, PaymentEvent, User


def client():
    cfg = settings()
    if not cfg.stripe_api_key.startswith(("rk_test_", "sk_test_")):
        raise HTTPException(503, "Test payments are not configured. Contact your Nebula operator.")
    return stripe.StripeClient(cfg.stripe_api_key, stripe_version=cfg.stripe_api_version, max_network_retries=1)


def checkout(db, user, cents, key):
    topup = db.scalar(select(Topup).where(Topup.user_id == user.id, Topup.key == key).with_for_update())
    if topup and topup.amount_cents != cents:
        raise HTTPException(409, "Idempotency key was already used for a different top-up")
    if not topup:
        topup = Topup(user_id=user.id, key=key, amount_cents=cents)
        db.add(topup)
        db.flush()
    if not topup.session_id:
        cfg = settings()
        result = client().v1.checkout.sessions.create(params={
            "mode": "payment", "customer_email": user.email,
            "client_reference_id": topup.id,
            "metadata": {"nebula_topup": topup.id},
            "integration_identifier": cfg.stripe_integration_id,
            "line_items": [{"price_data": {"currency": "usd", "unit_amount": cents,
                "product_data": {"name": "Nebula prepaid test credit"}}, "quantity": 1}],
            "success_url": cfg.public_url + "/?checkout=pending",
            "cancel_url": cfg.public_url + "/?checkout=cancelled",
        }, options={"idempotency_key": f"nebula-topup-{topup.id}"})
        if result.livemode:
            raise HTTPException(503, "Live Checkout sessions are disabled")
        topup.session_id, topup.checkout_url = result.id, result.url
    return {"url": topup.checkout_url, "session_id": topup.session_id}


def verify_event(payload, signature):
    secret = settings().stripe_webhook_secret
    if not secret:
        raise HTTPException(503, "Stripe webhook signing secret is missing")
    try:
        event = stripe.Webhook.construct_event(payload, signature or "", secret, tolerance=300).to_dict()
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(400, "Invalid Stripe webhook signature") from exc
    if event.get("livemode"):
        raise HTTPException(400, "Live Stripe events are disabled")
    return event


def fulfill(db, event):
    if db.get(PaymentEvent, event["id"]):
        return
    kind = event["type"]
    if kind not in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        db.add(PaymentEvent(id=event["id"], kind=kind))
        return
    obj = event["data"]["object"]
    topup = db.scalar(select(Topup).where(Topup.session_id == obj["id"]))
    # A callback can beat the transaction that saved Checkout's ID. Retry delivery.
    if not topup:
        raise HTTPException(503, "Checkout session not yet linked; retry webhook")
    user = db.scalar(select(User).where(User.id == topup.user_id).with_for_update())
    topup = db.scalar(select(Topup).where(Topup.id == topup.id).with_for_update().execution_options(populate_existing=True))
    current = client().v1.checkout.sessions.retrieve(obj["id"]).to_dict()
    if current["livemode"] or current["currency"] != "usd" or current["amount_total"] != topup.amount_cents:
        raise HTTPException(400, "Checkout amount, currency or environment mismatch")
    if current["client_reference_id"] != topup.id or current["metadata"].get("nebula_topup") != topup.id:
        raise HTTPException(400, "Checkout top-up ownership mismatch")
    if current["payment_status"] == "paid" and not topup.fulfilled:
        journal(db, user, "stripe:" + current["id"], topup.amount_cents * 10_000, "topup", {"stripe_session": current["id"]})
        topup.fulfilled = True
    # Serialize different event IDs for the same wallet/session with the user row lock.
    if not db.get(PaymentEvent, event["id"]):
        db.add(PaymentEvent(id=event["id"], kind=kind))
