"""Razorpay flow against the in-process mock gateway: create-order, verify, webhooks, failures, refunds."""
import json

import pytest
from sqlalchemy import func, select

from app.models import InventoryMovement, InventoryReservation, Order, Payment, PaymentEvent, Refund
from app.tests.conftest import inv, mock_pay, pay_order, place_order, start_payment, verify

API = "/api/v1/payments/razorpay"
GLD = "JW-EAR-001-GLD"


@pytest.fixture
def pending(client, catalog, users, cust_h):
    """A razorpay order for 2 x gold jhumka (reserved, unpaid) with a gateway order created."""
    order = place_order(client, cust_h, [(catalog.vid(GLD), 2)])
    data = start_payment(client, cust_h, order)
    return {"order": order, "rzp": data, "vid": catalog.vid(GLD), "h": cust_h}


def _order(db, oid) -> Order:
    db.expire_all()
    return db.get(Order, oid)


def _sales(db, vid) -> int:
    return db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.variant_id == vid,
                                                                   InventoryMovement.movement_type == "sale"))


def _webhook(client, gateway, event, entity, event_id=None, signature=None):
    body, sig, eid = gateway.build_webhook(event, entity)
    return client.post(f"{API}/webhook", content=body, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": signature or sig, "X-Razorpay-Event-Id": event_id or eid})


def _captured_entity(gateway, rzp_order_id, amount, pid=None):
    pid = pid or gateway.simulate_payment(rzp_order_id, amount, "upi", True)["payment"]["id"]
    return {"id": pid, "order_id": rzp_order_id, "amount": amount, "currency": "INR", "status": "captured", "method": "upi"}


# ----------------------------------------------------------------------------- happy path
def test_create_order_returns_checkout_options(pending):
    d = pending["rzp"]
    assert d["mode"] == "mock" and d["key_id"]
    assert d["razorpay_order_id"].startswith("order_mock_")
    assert d["amount"] == 179800  # paise, 2 x 899 with free shipping
    assert d["currency"] == "INR"
    assert d["prefill"]["email"] == "priya@test.example.com"


def test_create_order_reuses_open_gateway_order(client, db, pending):
    again = start_payment(client, pending["h"], pending["order"])
    assert again["razorpay_order_id"] == pending["rzp"]["razorpay_order_id"]
    assert db.scalar(select(func.count(Payment.id))) == 1


def test_full_mock_flow_marks_order_paid_and_commits_stock(client, db, pending):
    sim = mock_pay(client, pending["rzp"]["razorpay_order_id"])
    assert sim["status"] == "success"
    r = verify(client, sim)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "paid"
    assert body["order"]["status"] == "payment_confirmed"

    o = _order(db, pending["order"]["id"])
    assert o.payment_status == "paid" and o.paid_at is not None
    p = o.payments[0]
    assert p.status == "captured" and p.razorpay_payment_id == sim["razorpay_payment_id"] and p.method == "upi"
    i = inv(db, pending["vid"])
    assert (i.quantity_on_hand, i.quantity_reserved) == (8, 0)
    assert _sales(db, pending["vid"]) == 1
    resv = db.scalar(select(InventoryReservation).where(InventoryReservation.order_id == o.id))
    assert resv.status == "committed"


def test_duplicate_verify_is_idempotent(client, db, pending, outbox):
    sim = mock_pay(client, pending["rzp"]["razorpay_order_id"])
    assert verify(client, sim).status_code == 200
    second = verify(client, sim)
    assert second.status_code == 200 and second.json()["status"] == "paid"
    assert _sales(db, pending["vid"]) == 1
    assert db.scalar(select(func.count(Payment.id)).where(Payment.status == "captured")) == 1
    assert inv(db, pending["vid"]).quantity_on_hand == 8
    assert len([m for m in outbox if m["template"] == "order_confirmed"]) == 1


def test_invalid_signature_rejected(client, db, pending):
    sim = mock_pay(client, pending["rzp"]["razorpay_order_id"])
    sim["razorpay_signature"] = "0" * 64
    r = verify(client, sim)
    assert r.status_code == 402
    assert r.json()["error"]["code"] == "invalid_signature"
    o = _order(db, pending["order"]["id"])
    assert o.payment_status == "pending" and o.status == "payment_pending"
    assert inv(db, pending["vid"]).quantity_reserved == 2
    ev = db.scalar(select(PaymentEvent).where(PaymentEvent.source == "verify"))
    assert ev.signature_valid is False and ev.processing_result == "rejected"


def test_signature_for_other_order_rejected(client, db, catalog, pending, cust_h):
    other = place_order(client, cust_h, [(catalog.vid("AP-KRT-001-S"), 1)])
    other_rzp = start_payment(client, cust_h, other)
    sim = mock_pay(client, other_rzp["razorpay_order_id"])
    sim["razorpay_order_id"] = pending["rzp"]["razorpay_order_id"]  # replay a valid signature against another order
    assert verify(client, sim).status_code == 402
    assert _order(db, pending["order"]["id"]).payment_status == "pending"


# ----------------------------------------------------------------------------- webhooks
def test_webhook_payment_captured_marks_paid(client, db, gateway, pending):
    entity = _captured_entity(gateway, pending["rzp"]["razorpay_order_id"], pending["rzp"]["amount"])
    r = _webhook(client, gateway, "payment.captured", entity)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "processed"
    o = _order(db, pending["order"]["id"])
    assert o.payment_status == "paid" and o.status == "payment_confirmed"
    assert inv(db, pending["vid"]).quantity_on_hand == 8


def test_duplicate_webhook_event_is_ignored(client, db, gateway, pending):
    entity = _captured_entity(gateway, pending["rzp"]["razorpay_order_id"], pending["rzp"]["amount"])
    body, sig, eid = gateway.build_webhook("payment.captured", entity)
    headers = {"Content-Type": "application/json", "X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": eid}
    first = client.post(f"{API}/webhook", content=body, headers=headers)
    second = client.post(f"{API}/webhook", content=body, headers=headers)
    assert first.json()["status"] == "processed"
    assert second.status_code == 200 and second.json() == {"status": "duplicate", "event_id": eid}
    assert _sales(db, pending["vid"]) == 1
    assert db.scalar(select(func.count(PaymentEvent.id)).where(PaymentEvent.event_id == eid)) == 1


def test_webhook_bad_signature_rejected(client, db, gateway, pending):
    entity = _captured_entity(gateway, pending["rzp"]["razorpay_order_id"], pending["rzp"]["amount"])
    r = _webhook(client, gateway, "payment.captured", entity, signature="deadbeef" * 8)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_signature"
    assert _order(db, pending["order"]["id"]).payment_status == "pending"
    ev = db.scalar(select(PaymentEvent).where(PaymentEvent.signature_valid.is_(False)))
    assert ev is not None and ev.payload is None


def test_webhook_tampered_body_rejected(client, db, gateway, pending):
    entity = _captured_entity(gateway, pending["rzp"]["razorpay_order_id"], pending["rzp"]["amount"])
    body, sig, eid = gateway.build_webhook("payment.captured", entity)
    tampered = body.replace(b'"upi"', b'"card"')
    r = client.post(f"{API}/webhook", content=tampered, headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": eid})
    assert r.status_code == 422


def test_webhook_before_verify_then_verify_is_noop(client, db, gateway, pending):
    sim = mock_pay(client, pending["rzp"]["razorpay_order_id"])
    entity = gateway.fetch_payment(sim["razorpay_payment_id"])
    assert _webhook(client, gateway, "payment.captured", entity).json()["status"] == "processed"
    assert _order(db, pending["order"]["id"]).payment_status == "paid"

    r = verify(client, sim)
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert _sales(db, pending["vid"]) == 1
    o = _order(db, pending["order"]["id"])
    assert len(o.payments) == 1 and o.refunds == []
    assert inv(db, pending["vid"]).quantity_on_hand == 8


def test_webhook_amount_mismatch_not_marked_paid(client, db, gateway, pending):
    entity = _captured_entity(gateway, pending["rzp"]["razorpay_order_id"], 100)
    r = _webhook(client, gateway, "payment.captured", entity)
    assert r.status_code == 200
    assert r.json()["status"] == "amount_mismatch"
    o = _order(db, pending["order"]["id"])
    assert o.payment_status == "pending" and o.status == "payment_pending"
    assert inv(db, pending["vid"]).quantity_reserved == 2


def test_webhook_for_unknown_order_ignored(client, gateway, pending):
    entity = {"id": "pay_x", "order_id": "order_unknown", "amount": 100, "status": "captured"}
    assert _webhook(client, gateway, "payment.captured", entity).json()["status"] == "ignored_unknown_order"


def test_webhook_payment_failed_releases_stock(client, db, gateway, pending):
    entity = {"id": "pay_mock_failed1", "order_id": pending["rzp"]["razorpay_order_id"], "amount": pending["rzp"]["amount"],
              "status": "failed", "error_code": "BAD_REQUEST_ERROR", "error_description": "declined"}
    assert _webhook(client, gateway, "payment.failed", entity).json()["status"] == "processed"
    o = _order(db, pending["order"]["id"])
    assert o.payment_status == "failed" and o.status == "payment_pending"
    assert inv(db, pending["vid"]).quantity_reserved == 0


# ----------------------------------------------------------------------------- failures & retries
def test_failed_payment_releases_reservation_and_order_is_retryable(client, db, pending):
    sim = mock_pay(client, pending["rzp"]["razorpay_order_id"], outcome="failure")
    assert sim["status"] == "failed"
    r = client.post(f"{API}/failed", json={"razorpay_order_id": sim["razorpay_order_id"],
                                           "razorpay_payment_id": sim["razorpay_payment_id"],
                                           "error_code": sim["error"]["code"], "error_description": sim["error"]["description"]})
    assert r.status_code == 200 and r.json()["status"] == "failed"
    o = _order(db, pending["order"]["id"])
    assert o.status == "payment_pending" and o.payment_status == "failed"
    assert inv(db, pending["vid"]).quantity_reserved == 0
    status = client.get(f"/api/v1/payments/status/{o.id}", headers=pending["h"]).json()
    assert status["can_retry"] is True and status["last_error"]

    retry = start_payment(client, pending["h"], pending["order"])
    assert retry["razorpay_order_id"] != pending["rzp"]["razorpay_order_id"]
    assert inv(db, pending["vid"]).quantity_reserved == 2
    assert _order(db, o.id).payment_status == "pending"

    paid = verify(client, mock_pay(client, retry["razorpay_order_id"]))
    assert paid.json()["status"] == "paid"
    i = inv(db, pending["vid"])
    assert (i.quantity_on_hand, i.quantity_reserved) == (8, 0)


def test_client_reported_failure_is_confirmed_with_gateway(client, db, pending):
    """A browser claiming failure for a payment the gateway shows as captured must not fail the order."""
    sim = mock_pay(client, pending["rzp"]["razorpay_order_id"], outcome="success")
    r = client.post(f"{API}/failed", json={"razorpay_order_id": sim["razorpay_order_id"],
                                           "razorpay_payment_id": sim["razorpay_payment_id"], "error_code": "X"})
    assert r.status_code == 200
    o = _order(db, pending["order"]["id"])
    assert o.payment_status == "paid"


def test_late_payment_after_cancellation_is_refunded(client, db, gateway, pending):
    r = client.post(f"/api/v1/orders/{pending['order']['id']}/cancel", json={"reason": "changed my mind"}, headers=pending["h"])
    assert r.status_code == 200
    assert _order(db, pending["order"]["id"]).status == "cancelled"
    assert inv(db, pending["vid"]).quantity_reserved == 0

    entity = _captured_entity(gateway, pending["rzp"]["razorpay_order_id"], pending["rzp"]["amount"])
    assert _webhook(client, gateway, "payment.captured", entity).json()["status"] == "processed"
    o = _order(db, pending["order"]["id"])
    assert o.status == "refunded"
    assert o.payment_status == "refunded"
    assert len(o.refunds) == 1 and o.refunds[0].amount_paise == pending["rzp"]["amount"]
    assert o.refunds[0].idempotency_key.startswith("late:")
    i = inv(db, pending["vid"])
    assert (i.quantity_on_hand, i.quantity_reserved) == (10, 0)  # nothing was sold
    assert _sales(db, pending["vid"]) == 0


def test_cannot_start_payment_for_paid_or_cancelled_order(client, pending):
    pay_order(client, pending["h"], pending["order"])
    r = client.post(f"{API}/create-order", json={"order_id": str(pending["order"]["id"])}, headers=pending["h"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_paid"


def test_double_payment_refunds_the_duplicate(client, db, gateway, pending):
    first = mock_pay(client, pending["rzp"]["razorpay_order_id"])
    assert verify(client, first).json()["status"] == "paid"

    # The customer pays again from a second tab; the gateway reports it via webhook on a second Razorpay order.
    o = _order(db, pending["order"]["id"])
    dup_rzp = gateway.create_order(pending["rzp"]["amount"], "INR", o.order_number, {})
    db.add(Payment(order_id=o.id, provider="razorpay", mode="mock", razorpay_order_id=dup_rzp.id, amount_paise=dup_rzp.amount,
                   currency="INR", status="created", attempts=1, amount_refunded_paise=0))
    db.commit()
    entity = _captured_entity(gateway, dup_rzp.id, dup_rzp.amount)
    assert _webhook(client, gateway, "payment.captured", entity).json()["status"] == "processed"

    o = _order(db, pending["order"]["id"])
    refunds = db.scalars(select(Refund).where(Refund.order_id == o.id)).all()
    assert len(refunds) == 1
    assert refunds[0].idempotency_key.startswith("dup:")
    assert refunds[0].amount_paise == dup_rzp.amount and refunds[0].status == "processed"
    dup = db.scalar(select(Payment).where(Payment.razorpay_order_id == dup_rzp.id))
    assert dup.status == "refunded"
    original = db.scalar(select(Payment).where(Payment.razorpay_order_id == pending["rzp"]["razorpay_order_id"]))
    assert original.status == "captured" and original.amount_refunded_paise == 0
    # the order itself remains a paid, confirmed order with stock committed once
    assert o.status == "payment_confirmed"
    assert o.payment_status == "paid"
    assert o.refunded_total == 0
    assert _sales(db, pending["vid"]) == 1


def test_refund_webhook_updates_refund_status(client, db, gateway, admin_h, pending):
    paid = pay_order(client, pending["h"], pending["order"])
    r = client.post(f"/api/v1/admin/orders/{paid['id']}/refunds", json={"amount": "100.00", "reason": "price adjustment"}, headers=admin_h)
    assert r.status_code == 201
    refund = db.scalar(select(Refund).where(Refund.order_id == paid["id"]))
    body, sig, eid = gateway.build_webhook("refund.processed", {"id": refund.razorpay_refund_id, "amount": 10000}, entity_name="refund")
    resp = client.post(f"{API}/webhook", content=body, headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": eid})
    assert resp.json()["status"] == "processed"


def test_payment_events_do_not_store_sensitive_fields(client, db, gateway, pending):
    entity = _captured_entity(gateway, pending["rzp"]["razorpay_order_id"], pending["rzp"]["amount"])
    entity.update({"card": {"last4": "1111"}, "vpa": "priya@upi", "contact": "+919810012345", "email": "p@example.com"})
    _webhook(client, gateway, "payment.captured", entity)
    ev = db.scalar(select(PaymentEvent).where(PaymentEvent.source == "webhook"))
    dumped = json.dumps(ev.payload)
    for secret in ("1111", "priya@upi", "9810012345", "p@example.com"):
        assert secret not in dumped
