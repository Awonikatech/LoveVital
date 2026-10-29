"""Razorpay payments: order creation, verification, webhooks, refunds.

Idempotency guarantees
  * One `payments` row per Razorpay order id (UNIQUE) and per Razorpay payment id (UNIQUE).
  * Every verify callback and webhook is recorded in `payment_events` with a UNIQUE `event_id`
    (`X-Razorpay-Event-Id` for webhooks, `verify:<payment_id>` for callbacks); a duplicate insert
    means "already processed" and is acknowledged without side effects.
  * `mark_paid` is a no-op when the payment is already captured, so callback + webhook racing for
    the same payment converge on one state change (row locked with SELECT ... FOR UPDATE).
  * Refunds carry a UNIQUE idempotency key (e.g. `cancel:<order_id>`, `return:<return_id>`), and the
    same key is forwarded to Razorpay as the refund receipt.
  * An order is marked paid only after server-side signature verification (and, in test/live mode,
    a server-side fetch confirming status=captured and the exact amount)."""
from __future__ import annotations

import json
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import AppError, Conflict, NotFound, ValidationFailed
from app.core.money import D, from_paise, q, to_paise
from app.integrations.razorpay_gateway import GatewayError, MockRazorpayGateway, get_gateway
from app.models import InventoryReservation, Order, Payment, PaymentEvent, Refund, User
from app.services import inventory_service, order_service

log = logging.getLogger("app.payments")


class PaymentError(AppError):
    status_code = 402
    code = "payment_error"


# ------------------------------------------------------------------ events
def record_event(db: Session, event_id: str, event_type: str, source: str, payload: dict | None,
                 signature_valid: bool, payment: Payment | None = None) -> PaymentEvent | None:
    """Insert the event; returns None if this event_id was already recorded (duplicate)."""
    existing = db.scalar(select(PaymentEvent).where(PaymentEvent.event_id == event_id))
    if existing:
        return None
    ev = PaymentEvent(event_id=event_id, event_type=event_type, source=source, payload=_sanitize(payload),
                      signature_valid=signature_valid, payment_id=payment.id if payment else None)
    try:
        with db.begin_nested():
            db.add(ev)
            db.flush()
    except IntegrityError:
        return None
    return ev


def _sanitize(payload: dict | None) -> dict | None:
    """Keep only non-sensitive fields from gateway payloads (no card numbers, VPAs, contacts)."""
    if not payload:
        return payload
    blocked = {"card", "vpa", "contact", "email", "bank_account", "token", "razorpay_signature", "signature"}

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items() if k not in blocked}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o

    return clean(payload)


# ------------------------------------------------------------------ create
def create_payment_order(db: Session, order: Order) -> dict:
    order = db.scalar(select(Order).where(Order.id == order.id).with_for_update())
    if order.payment_method != "razorpay":
        raise Conflict("This order is not an online-payment order")
    if order.payment_status == "paid":
        raise Conflict("This order has already been paid", code="already_paid")
    if order.status != "payment_pending":
        raise Conflict("This order can no longer be paid. Please place a new order.", code="not_payable")
    # Retry after a failed attempt or expired hold: make sure stock is held again.
    active = db.scalar(select(InventoryReservation.id).where(
        InventoryReservation.order_id == order.id, InventoryReservation.status == "active", InventoryReservation.expires_at > utcnow()))
    if not active:
        stale = db.scalars(select(InventoryReservation).where(InventoryReservation.order_id == order.id)).all()
        for r in stale:
            if r.status == "active":
                inventory_service.release(db, order, "retry_refresh")
                break
        for r in db.scalars(select(InventoryReservation).where(InventoryReservation.order_id == order.id, InventoryReservation.status != "committed")).all():
            db.delete(r)
        db.flush()
        wanted: dict[int, int] = {}
        for it in order.items:
            if it.variant_id:
                wanted[it.variant_id] = wanted.get(it.variant_id, 0) + it.quantity
        inventory_service.reserve(db, order, wanted)

    gw = get_gateway(db)
    amount = to_paise(order.grand_total)
    payment = db.scalar(select(Payment).where(Payment.order_id == order.id, Payment.status == "created",
                                              Payment.amount_paise == amount).order_by(Payment.id.desc()))
    if payment is None:
        try:
            go = gw.create_order(amount, order.currency, order.order_number,
                                 {"order_number": order.order_number, "order_id": str(order.id)})
        except GatewayError as e:
            log.warning("gateway create_order failed for %s: %s", order.order_number, e)
            raise PaymentError("We couldn't start the payment. Please try again in a moment.", code="gateway_unavailable")
        payment = Payment(order_id=order.id, provider="razorpay", mode=gw.mode, razorpay_order_id=go.id,
                          amount_paise=go.amount, currency=go.currency, status="created", attempts=0, amount_refunded_paise=0)
        db.add(payment)
    payment.attempts += 1
    if order.payment_status == "failed":
        order.payment_status = "pending"
    db.flush()
    ship = order.address("shipping")
    return {
        "key_id": gw.key_id,
        "mode": gw.mode,
        "razorpay_order_id": payment.razorpay_order_id,
        "amount": payment.amount_paise,
        "currency": payment.currency,
        "name": settings.APP_NAME,
        "description": f"Order {order.order_number}",
        "order_number": order.order_number,
        "order_id": order.id,
        "prefill": {"name": ship.full_name if ship else "", "email": order.email, "contact": order.phone or (ship.phone if ship else "")},
        "theme_color": "#B8860B",
    }


# ------------------------------------------------------------------ verify (checkout callback)
def verify_payment(db: Session, razorpay_order_id: str, razorpay_payment_id: str, signature: str) -> Order:
    gw = get_gateway(db)
    payment = db.scalar(select(Payment).where(Payment.razorpay_order_id == razorpay_order_id).with_for_update())
    if not payment:
        raise NotFound("Payment not found", code="payment_not_found")
    valid = gw.verify_payment_signature(razorpay_order_id, razorpay_payment_id, signature)
    ev = record_event(db, f"verify:{razorpay_payment_id}", "checkout.verify", "verify",
                      {"razorpay_order_id": razorpay_order_id, "razorpay_payment_id": razorpay_payment_id},
                      signature_valid=valid, payment=payment)
    if not valid:
        if ev:
            ev.processing_result, ev.error, ev.processed_at = "rejected", "invalid signature", utcnow()
        db.commit()
        raise PaymentError("Payment verification failed. If money was debited it will be auto-refunded.", code="invalid_signature")
    order = db.scalar(select(Order).where(Order.id == payment.order_id).with_for_update())
    if payment.status == "captured" and payment.razorpay_payment_id == razorpay_payment_id:
        if ev:
            ev.processing_result, ev.processed_at = "duplicate", utcnow()
        return order
    # In test/live, confirm with Razorpay server-side before trusting the callback.
    method = None
    try:
        info = gw.fetch_payment(razorpay_payment_id)
        method = info.get("method")
        if info.get("order_id") not in (None, razorpay_order_id) or int(info.get("amount", payment.amount_paise)) != payment.amount_paise:
            raise PaymentError("Payment details do not match the order", code="amount_mismatch")
        if info.get("status") not in ("captured", "authorized"):
            raise PaymentError("Payment is not yet captured. We'll update your order shortly.", code="payment_pending")
    except GatewayError as e:
        if gw.mode != "mock":
            log.warning("fetch_payment failed, relying on signature for %s: %s", razorpay_payment_id, e)
    payment.razorpay_signature = signature
    mark_paid(db, payment, order, razorpay_payment_id, method, source="verify")
    if ev:
        ev.processing_result, ev.processed_at = "processed", utcnow()
    return order


def mark_paid(db: Session, payment: Payment, order: Order, razorpay_payment_id: str, method: str | None, source: str) -> None:
    if payment.status == "captured":
        return
    payment.status = "captured"
    payment.razorpay_payment_id = razorpay_payment_id
    payment.method = method or payment.method
    payment.captured_at = utcnow()
    payment.error_code = payment.error_description = None
    if order.payment_status == "paid":
        # A different payment already settled this order (double payment) -> refund this one.
        db.flush()
        _refund_payment(db, order, payment, payment.amount_paise, "Duplicate payment for an already-paid order", None,
                        f"dup:{payment.id}", affects_order=False)
        return
    order.payment_status = "paid"
    order.paid_at = utcnow()
    if order.status == "cancelled":
        # Payment landed after the hold expired and the order was auto-cancelled: refund in full.
        db.flush()
        _refund_payment(db, order, payment, payment.amount_paise, "Payment received after order was cancelled", None,
                        f"late:{payment.id}")
        order_service.transition(db, order, "refund_initiated", actor=None, note="Late payment refunded", actor_type="system")
        _maybe_mark_refunded(db, order)
        return
    if not inventory_service.commit(db, order):
        order_service.transition(db, order, "payment_confirmed", actor=None, note=f"Payment captured via {source}", actor_type="system")
        order_service.transition(db, order, "cancelled", actor=None, note="Stock sold out before payment completed", actor_type="system")
        order.cancellation_reason = "Item went out of stock before payment completed"
        order_service.reverse_coupon(db, order)
        db.flush()
        _refund_payment(db, order, payment, payment.amount_paise, "Out of stock after payment", None, f"oos:{payment.id}")
        order_service.transition(db, order, "refund_initiated", actor=None, note="Auto refund", actor_type="system")
        _maybe_mark_refunded(db, order)
        return
    order_service.transition(db, order, "payment_confirmed", actor=None, note=f"Payment captured via {source}", actor_type="system")
    db.flush()
    _notify_order_confirmed(order)


def _notify_order_confirmed(order: Order) -> None:
    from app.services.notification_service import queue_order_email

    queue_order_email(order, "order_confirmed")


def report_failure(db: Session, razorpay_order_id: str, razorpay_payment_id: str | None, code: str | None, description: str | None) -> Order:
    payment = db.scalar(select(Payment).where(Payment.razorpay_order_id == razorpay_order_id).with_for_update())
    if not payment:
        raise NotFound("Payment not found")
    order = db.get(Order, payment.order_id)
    if payment.status == "captured":
        return order
    if razorpay_payment_id:
        # Never trust the browser for state; confirm the failure with the gateway.
        try:
            info = get_gateway(db).fetch_payment(razorpay_payment_id)
            if info.get("status") == "captured":
                mark_paid(db, payment, order, razorpay_payment_id, info.get("method"), source="failure-recheck")
                return order
            if info.get("status") != "failed":
                return order
        except GatewayError:
            return order
    record_event(db, f"client-failure:{razorpay_payment_id or secrets.token_hex(6)}", "payment.failed", "verify",
                 {"code": code, "description": description}, signature_valid=False, payment=payment)
    _mark_failed(db, payment, order, code, description)
    return order


def _mark_failed(db: Session, payment: Payment, order: Order, code: str | None, desc: str | None) -> None:
    if payment.status == "captured":
        return
    payment.status = "failed"
    payment.error_code = (code or "")[:80] or None
    payment.error_description = (desc or "")[:300] or None
    if order.payment_status != "paid":
        order.payment_status = "failed"
        inventory_service.release(db, order, "payment_failed")
    db.flush()


# ------------------------------------------------------------------ webhooks
def handle_webhook(db: Session, raw_body: bytes, signature: str | None, event_id: str | None) -> dict:
    gw = get_gateway(db)
    valid = gw.verify_webhook_signature(raw_body, signature or "")
    try:
        data = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        data = {}
    etype = data.get("event", "unknown")
    if not valid:
        record_event(db, f"invalid:{secrets.token_hex(10)}", etype, "webhook", None, signature_valid=False)
        db.commit()
        raise ValidationFailed("Invalid webhook signature", code="invalid_signature")
    eid = event_id or f"{etype}:{_entity_id(data)}"
    ev = record_event(db, eid, etype, "webhook", data, signature_valid=True)
    if ev is None:
        return {"status": "duplicate", "event_id": eid}
    try:
        result = _dispatch(db, etype, data, ev)
        ev.processing_result, ev.processed_at = result, utcnow()
    except AppError as e:
        ev.processing_result, ev.error, ev.processed_at = "error", e.message[:500], utcnow()
    db.commit()
    return {"status": ev.processing_result, "event_id": eid}


def _entity_id(data: dict) -> str:
    for key in ("refund", "payment", "order"):
        ent = (data.get("payload", {}).get(key) or {}).get("entity") or {}
        if ent.get("id"):
            return ent["id"]
    return secrets.token_hex(6)


def _dispatch(db: Session, etype: str, data: dict, ev: PaymentEvent) -> str:
    payload = data.get("payload", {})
    if etype in ("payment.captured", "order.paid", "payment.failed", "payment.authorized"):
        pay = (payload.get("payment") or {}).get("entity") or {}
        rzp_order_id = pay.get("order_id") or ((payload.get("order") or {}).get("entity") or {}).get("id")
        payment = db.scalar(select(Payment).where(Payment.razorpay_order_id == rzp_order_id).with_for_update())
        if not payment:
            return "ignored_unknown_order"
        ev.payment_id = payment.id
        order = db.scalar(select(Order).where(Order.id == payment.order_id).with_for_update())
        if etype in ("payment.captured", "order.paid"):
            if int(pay.get("amount", payment.amount_paise)) != payment.amount_paise:
                return "amount_mismatch"
            mark_paid(db, payment, order, pay.get("id") or payment.razorpay_payment_id, pay.get("method"), source="webhook")
            return "processed"
        if etype == "payment.failed":
            _mark_failed(db, payment, order, pay.get("error_code"), pay.get("error_description"))
            return "processed"
        return "ignored"
    if etype in ("refund.processed", "refund.failed"):
        ref = (payload.get("refund") or {}).get("entity") or {}
        refund = db.scalar(select(Refund).where(Refund.razorpay_refund_id == ref.get("id")).with_for_update())
        if not refund:
            return "ignored_unknown_refund"
        order = db.get(Order, refund.order_id)
        if etype == "refund.processed" and refund.status != "processed":
            refund.status, refund.processed_at = "processed", utcnow()
            _maybe_mark_refunded(db, order)
        elif etype == "refund.failed" and refund.status != "processed":
            refund.status = "failed"
            pay = db.get(Payment, refund.payment_id) if refund.payment_id else None
            if pay:
                pay.amount_refunded_paise = max(0, pay.amount_refunded_paise - refund.amount_paise)
            if not refund.idempotency_key.startswith("dup:"):  # duplicate-payment refunds never counted on the order
                order.refunded_total = q(max(D(0), order.refunded_total - from_paise(refund.amount_paise)))
        return "processed"
    return "ignored"


# ------------------------------------------------------------------ refunds
def refund_order(db: Session, order: Order, *, amount, reason: str, actor: User | None, idempotency_key: str | None = None) -> Refund | None:
    key = idempotency_key or f"manual:{order.id}:{secrets.token_hex(6)}"
    existing = db.scalar(select(Refund).where(Refund.idempotency_key == key))
    if existing:
        return existing
    if order.payment_status not in ("paid", "partially_refunded"):
        raise Conflict("Order has no captured payment to refund", code="not_paid")
    payment = next((p for p in order.payments if p.status in ("captured", "partially_refunded", "cod_collected")), None)
    if not payment:
        raise Conflict("No captured payment found", code="not_paid")
    refundable = payment.amount_paise - payment.amount_refunded_paise
    amt = refundable if amount is None else to_paise(amount)
    if amt <= 0:
        raise ValidationFailed("Refund amount must be positive")
    if amt > refundable:
        raise ValidationFailed(f"Maximum refundable amount is ₹{from_paise(refundable)}", code="refund_exceeds_paid")
    refund = _refund_payment(db, order, payment, amt, reason, actor, key)
    if order.status in ("cancelled", "returned"):
        order_service.transition(db, order, "refund_initiated", actor=actor, note=reason[:300],
                                 actor_type="admin" if actor and actor.is_staff else "system")
    _maybe_mark_refunded(db, order)
    return refund


def _refund_payment(db: Session, order: Order, payment: Payment, amount_paise: int, reason: str, actor: User | None, key: str,
                    affects_order: bool = True) -> Refund:
    """Refund `amount_paise` of `payment`. `affects_order=False` is for returning a duplicate payment: the money never
    counted towards the order, so the order's payment status and refunded total stay as they are."""
    refund = Refund(order_id=order.id, payment_id=payment.id, idempotency_key=key, amount_paise=amount_paise,
                    status="pending", reason=reason[:300], initiated_by_id=actor.id if actor else None)
    db.add(refund)
    db.flush()
    if payment.provider == "cod":
        # COD refunds are paid out manually (bank transfer/UPI) by the finance team.
        refund.status, refund.processed_at = "processed", utcnow()
    else:
        gw = get_gateway(db)
        if payment.mode != gw.mode:
            refund.status = "failed"
            db.flush()
            raise PaymentError(f"This payment was taken in Razorpay {payment.mode} mode but the gateway is now in {gw.mode} mode. "
                               "Switch the gateway back to refund it, or refund it from the Razorpay dashboard.", code="refund_mode_mismatch")
        try:
            r = gw.refund(payment.razorpay_payment_id, amount_paise, {"order_number": order.order_number, "reason": reason[:200]}, key)
        except GatewayError as e:
            refund.status = "failed"
            db.flush()
            raise PaymentError(f"Refund could not be initiated: {e}", code="refund_failed")
        refund.razorpay_refund_id = r.get("id")
        if r.get("status") == "processed":
            refund.status, refund.processed_at = "processed", utcnow()
    payment.amount_refunded_paise += amount_paise
    payment.status = "refunded" if payment.amount_refunded_paise >= payment.amount_paise else "partially_refunded"
    if affects_order:
        order.refunded_total = q(order.refunded_total + from_paise(amount_paise))
        order.payment_status = "refunded" if payment.amount_refunded_paise >= payment.amount_paise else "partially_refunded"
    db.flush()
    from app.services.notification_service import queue_order_email

    queue_order_email(order, "refund_initiated", extra={"amount": f"{from_paise(amount_paise):.2f}"})
    return refund


def _maybe_mark_refunded(db: Session, order: Order) -> None:
    db.flush()
    refunds = db.scalars(select(Refund).where(Refund.order_id == order.id)).all()
    if order.status == "refund_initiated" and refunds and all(r.status in ("processed", "failed") for r in refunds) \
            and any(r.status == "processed" for r in refunds):
        order_service.transition(db, order, "refunded", actor=None, note="Refund processed", actor_type="system")


# ------------------------------------------------------------------ mock simulator (gateway in mock mode only)
def mock_checkout(db: Session, razorpay_order_id: str, succeed: bool, method: str) -> dict:
    gw = get_gateway(db)
    if not isinstance(gw, MockRazorpayGateway):
        raise NotFound("Not available")
    payment = db.scalar(select(Payment).where(Payment.razorpay_order_id == razorpay_order_id))
    if not payment:
        raise NotFound("Payment not found")
    sim = gw.simulate_payment(razorpay_order_id, payment.amount_paise, method, succeed)
    p = sim["payment"]
    if succeed:
        return {"status": "success", "razorpay_order_id": razorpay_order_id, "razorpay_payment_id": p["id"],
                "razorpay_signature": sim["signature"]}
    return {"status": "failed", "razorpay_order_id": razorpay_order_id, "razorpay_payment_id": p["id"],
            "error": {"code": p["error_code"], "description": p["error_description"]}}
