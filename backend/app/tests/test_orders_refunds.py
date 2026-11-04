"""Order lifecycle: cancellation, admin transitions, shipments, delivery, returns and refunds."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import Conflict
from app.models import AuditLog, Coupon, CouponRedemption, InventoryMovement, Order, Refund
from app.services import order_service, payment_service
from app.tests.conftest import inv, pay_order, place_order

API = "/api/v1"
ADMIN = "/api/v1/admin"
GLD = "JW-EAR-001-GLD"


def _order(db, oid) -> Order:
    db.expire_all()
    return db.get(Order, oid)


def _status(client, admin_h, oid, status, expect=200):
    r = client.post(f"{ADMIN}/orders/{oid}/status", json={"status": status}, headers=admin_h)
    assert r.status_code == expect, r.text
    return r.json()


def _ship(client, admin_h, oid, mark_shipped=True) -> dict:
    r = client.post(f"{ADMIN}/orders/{oid}/shipments", json={"mark_shipped": mark_shipped, "weight_grams": 300}, headers=admin_h)
    assert r.status_code == 201, r.text
    return r.json()


def _shipment_status(client, admin_h, sid, status, expect=200):
    r = client.post(f"{ADMIN}/shipments/{sid}/status", json={"status": status}, headers=admin_h)
    assert r.status_code == expect, r.text
    return r.json()


def _deliver(client, admin_h, oid) -> dict:
    _status(client, admin_h, oid, "processing")
    sid = _ship(client, admin_h, oid)["shipments"][0]["id"]
    _shipment_status(client, admin_h, sid, "out_for_delivery")
    return _shipment_status(client, admin_h, sid, "delivered")


@pytest.fixture
def paid_order(client, catalog, users, cust_h):
    order = place_order(client, cust_h, [(catalog.vid(GLD), 2)])
    return pay_order(client, cust_h, order)


# ----------------------------------------------------------------------------- customer cancellation
def test_customer_cancels_paid_order_gets_refund_restock_and_coupon_back(client, db, catalog, users, cust_h, outbox):
    coupon = Coupon(code="TENOFF", discount_type="percent", value=Decimal("10"), usage_limit_per_user=1)
    db.add(coupon)
    db.commit()
    vid = catalog.vid(GLD)
    order = pay_order(client, cust_h, place_order(client, cust_h, [(vid, 2)], coupon_code="TENOFF"))
    assert order["totals"]["coupon_discount"] == "179.80"
    db.expire_all()
    assert db.get(Coupon, coupon.id).times_used == 1
    assert inv(db, vid).quantity_on_hand == 8

    r = client.post(f"{API}/orders/{order['id']}/cancel", json={"reason": "Ordered by mistake"}, headers=cust_h)
    assert r.status_code == 200, r.text
    assert "cancelled" in r.json()["message"].lower()
    assert "refund has been initiated" in r.json()["message"]

    o = _order(db, order["id"])
    assert o.status == "refunded"
    assert o.payment_status == "refunded"
    assert o.refunded_total == Decimal(order["totals"]["grand_total"])
    assert [h.to_status for h in o.history][-3:] == ["cancelled", "refund_initiated", "refunded"]
    refund = db.scalar(select(Refund).where(Refund.order_id == o.id))
    assert refund.status == "processed" and refund.idempotency_key == f"cancel:{o.id}"
    assert refund.amount_paise == 161820 + 0  # 1798 - 179.80, free shipping
    i = inv(db, vid)
    assert (i.quantity_on_hand, i.quantity_reserved) == (10, 0)
    mv = db.scalars(select(InventoryMovement).where(InventoryMovement.variant_id == vid).order_by(InventoryMovement.id)).all()
    assert mv[-1].movement_type == "cancellation" and mv[-1].quantity == 2 and mv[-1].balance_after == 10
    assert db.get(Coupon, coupon.id).times_used == 0
    assert db.scalar(select(CouponRedemption).where(CouponRedemption.order_id == o.id)).status == "reversed"
    assert any(m["template"] == "order_cancelled" for m in outbox)
    assert any(m["template"] == "refund_initiated" for m in outbox)

    # cancelling again is rejected and does not refund twice
    again = client.post(f"{API}/orders/{order['id']}/cancel", json={"reason": "again"}, headers=cust_h)
    assert again.status_code == 409
    assert db.scalar(select(func.count(Refund.id))) == 1


def test_customer_cancels_unpaid_order_releases_reservation(client, db, catalog, users, cust_h):
    vid = catalog.vid(GLD)
    order = place_order(client, cust_h, [(vid, 2)])
    r = client.post(f"{API}/orders/{order['id']}/cancel", json={"reason": "Found it cheaper"}, headers=cust_h)
    assert r.status_code == 200
    assert r.json()["message"] == "Your order has been cancelled."
    o = _order(db, order["id"])
    assert o.status == "cancelled" and o.payment_status == "cancelled"
    assert o.refunds == []
    i = inv(db, vid)
    assert (i.quantity_on_hand, i.quantity_reserved) == (10, 0)


def test_cancel_packed_order_becomes_request_then_admin_approves(client, db, catalog, users, cust_h, admin_h, paid_order):
    oid = paid_order["id"]
    _status(client, admin_h, oid, "processing")
    _status(client, admin_h, oid, "packed")
    r = client.post(f"{API}/orders/{oid}/cancel", json={"reason": "Need it sooner"}, headers=cust_h)
    assert r.status_code == 200
    assert r.json()["order"]["status"] == "cancellation_requested"
    assert "requested" in r.json()["message"].lower()
    assert _order(db, oid).payment_status == "paid"

    r = client.post(f"{ADMIN}/orders/{oid}/cancellation-request", json={"approve": True}, headers=admin_h)
    assert r.status_code == 200, r.text
    o = _order(db, oid)
    assert o.status == "refunded" and o.payment_status == "refunded"
    assert o.cancellation_reason == "Need it sooner"
    assert inv(db, catalog.vid(GLD)).quantity_on_hand == 10


def test_cancel_request_rejected_restores_previous_status(client, db, cust_h, admin_h, paid_order):
    oid = paid_order["id"]
    _status(client, admin_h, oid, "processing")
    _status(client, admin_h, oid, "packed")
    client.post(f"{API}/orders/{oid}/cancel", json={"reason": "Need it sooner"}, headers=cust_h)
    r = client.post(f"{ADMIN}/orders/{oid}/cancellation-request", json={"approve": False, "note": "Already packed"}, headers=admin_h)
    assert r.status_code == 200
    o = _order(db, oid)
    assert o.status == "packed" and o.payment_status == "paid" and o.refunds == []
    # nothing pending any more
    again = client.post(f"{ADMIN}/orders/{oid}/cancellation-request", json={"approve": True}, headers=admin_h)
    assert again.status_code == 409


def test_cannot_cancel_after_shipped(client, db, cust_h, admin_h, paid_order):
    oid = paid_order["id"]
    _status(client, admin_h, oid, "processing")
    _ship(client, admin_h, oid)
    assert _order(db, oid).status == "shipped"
    r = client.post(f"{API}/orders/{oid}/cancel", json={"reason": "too late"}, headers=cust_h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_cancellable"
    r = client.post(f"{ADMIN}/orders/{oid}/cancel", json={"reason": "too late"}, headers=admin_h)
    assert r.status_code == 409


# ----------------------------------------------------------------------------- admin transitions
def test_admin_illegal_transitions_rejected(client, db, catalog, cust_h, admin_h):
    unpaid = place_order(client, cust_h, [(catalog.vid(GLD), 1)])
    r = client.post(f"{ADMIN}/orders/{unpaid['id']}/status", json={"status": "packed"}, headers=admin_h)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "invalid_transition"
    assert err["details"]["from"] == "payment_pending" and err["details"]["to"] == "packed"
    r = client.post(f"{ADMIN}/orders/{unpaid['id']}/status", json={"status": "delivered"}, headers=admin_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"


def test_unpaid_order_cannot_be_processed(client, db, catalog, cust_h, admin_h, users):
    unpaid = place_order(client, cust_h, [(catalog.vid(GLD), 1)])
    o = _order(db, unpaid["id"])
    with pytest.raises(Conflict) as exc:
        order_service.transition(db, o, "payment_confirmed", actor=users.admin)
    assert exc.value.code == "payment_required"
    db.rollback()


@pytest.mark.parametrize("target", ["shipped", "cancelled", "refunded", "returned", "payment_confirmed", "refund_initiated"])
def test_dedicated_action_statuses_rejected_via_status_endpoint(client, admin_h, paid_order, target):
    r = client.post(f"{ADMIN}/orders/{paid_order['id']}/status", json={"status": target}, headers=admin_h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "use_dedicated_action"


def test_shipped_requires_a_shipment(client, db, admin_h, paid_order, users):
    oid = paid_order["id"]
    _status(client, admin_h, oid, "processing")
    _status(client, admin_h, oid, "packed")
    o = _order(db, oid)
    with pytest.raises(Conflict) as exc:
        order_service.transition(db, o, "shipped", actor=users.admin)
    assert exc.value.code == "shipment_required"
    db.rollback()
    assert _order(db, oid).status == "packed"


def test_full_shipment_flow(client, db, admin_h, cust_h, paid_order, outbox):
    oid = paid_order["id"]
    assert _status(client, admin_h, oid, "processing")["status"] == "processing"
    d = _ship(client, admin_h, oid, mark_shipped=False)
    assert d["status"] == "packed"
    shipment = d["shipments"][0]
    assert shipment["tracking_number"].startswith("SWK") and shipment["status"] == "ready"

    # a second active shipment is refused
    assert client.post(f"{ADMIN}/orders/{oid}/shipments", json={}, headers=admin_h).status_code == 409

    sid = shipment["id"]
    assert _shipment_status(client, admin_h, sid, "shipped")["status"] == "shipped"
    assert _shipment_status(client, admin_h, sid, "in_transit")["status"] == "shipped"
    assert _shipment_status(client, admin_h, sid, "out_for_delivery")["status"] == "out_for_delivery"
    d = _shipment_status(client, admin_h, sid, "delivered")
    assert d["status"] == "delivered"
    assert d["delivered_at"] is not None
    assert d["shipments"][0]["status"] == "delivered"
    assert [h["to"] for h in d["history"]] == ["payment_pending", "payment_confirmed", "processing", "packed", "shipped",
                                             "out_for_delivery", "delivered"]

    track = client.get(f"{API}/track/{shipment['tracking_number']}")
    assert track.status_code == 200
    assert track.json()["order_status"] == "delivered"
    assert len(track.json()["events"]) == 4
    assert {"order_shipped", "order_delivered"} <= {m["template"] for m in outbox}

    customer_view = client.get(f"{API}/orders/{oid}", headers=cust_h).json()
    assert customer_view["can_return"] is True


def test_cod_order_paid_on_delivery(client, db, catalog, cust_h, admin_h):
    order = place_order(client, cust_h, [(catalog.vid(GLD), 1)], payment_method="cod")
    assert order["payment_status"] == "pending"
    _deliver(client, admin_h, order["id"])
    o = _order(db, order["id"])
    assert o.status == "delivered"
    assert o.payment_status == "paid" and o.paid_at is not None
    assert o.payments[0].status == "cod_collected"


def test_delivery_failed_then_reattempt(client, db, admin_h, paid_order):
    oid = paid_order["id"]
    _status(client, admin_h, oid, "processing")
    sid = _ship(client, admin_h, oid)["shipments"][0]["id"]
    assert _shipment_status(client, admin_h, sid, "delivery_failed")["status"] == "delivery_failed"
    assert _shipment_status(client, admin_h, sid, "shipped")["status"] == "shipped"


# ----------------------------------------------------------------------------- returns
def test_return_within_window_refunds_item_amount(client, db, catalog, cust_h, admin_h, paid_order):
    oid = paid_order["id"]
    _deliver(client, admin_h, oid)
    item = paid_order["items"][0]
    assert item["quantity"] == 2 and item["line_total"] == "1798.00"

    r = client.post(f"{API}/orders/{oid}/returns", headers=cust_h,
                    json={"reason": "size_issue", "items": [{"order_item_id": item["id"], "quantity": 1}]})
    assert r.status_code == 201, r.text
    rid = r.json()["return_id"]
    assert r.json()["order"]["status"] == "return_requested"

    # receiving before approval is refused
    assert client.post(f"{ADMIN}/returns/{rid}", json={"action": "receive"}, headers=admin_h).status_code == 409
    a = client.post(f"{ADMIN}/returns/{rid}", json={"action": "approve"}, headers=admin_h)
    assert a.status_code == 200 and a.json()["status"] == "approved"
    rec = client.post(f"{ADMIN}/returns/{rid}", json={"action": "receive", "note": "QC ok"}, headers=admin_h)
    assert rec.status_code == 200, rec.text
    assert rec.json()["status"] == "refunded"
    assert rec.json()["refund_amount"] == "899.00"

    o = _order(db, oid)
    assert o.items[0].returned_quantity == 1
    assert o.refunded_total == Decimal("899.00")
    assert o.payment_status == "partially_refunded"
    assert o.status == "refunded"
    refund = db.scalar(select(Refund).where(Refund.order_id == oid))
    assert refund.amount_paise == 89900 and refund.idempotency_key.startswith("return:")
    i = inv(db, catalog.vid(GLD))
    assert i.quantity_on_hand == 9  # 10 - 2 sold + 1 returned
    mv = db.scalars(select(InventoryMovement).where(InventoryMovement.movement_type == "return")).all()
    assert len(mv) == 1 and mv[0].quantity == 1 and mv[0].balance_after == 9


def test_return_rejected_restores_delivered(client, db, cust_h, admin_h, paid_order):
    oid = paid_order["id"]
    _deliver(client, admin_h, oid)
    rid = client.post(f"{API}/orders/{oid}/returns", headers=cust_h, json={
        "reason": "changed_mind", "items": [{"order_item_id": paid_order["items"][0]["id"], "quantity": 1}]}).json()["return_id"]
    r = client.post(f"{ADMIN}/returns/{rid}", json={"action": "reject", "note": "Worn item"}, headers=admin_h)
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert _order(db, oid).status == "delivered"


def test_return_outside_window_rejected(client, db, cust_h, admin_h, paid_order):
    oid = paid_order["id"]
    _deliver(client, admin_h, oid)
    o = _order(db, oid)
    o.delivered_at = o.delivered_at - timedelta(days=8)
    db.commit()
    r = client.post(f"{API}/orders/{oid}/returns", headers=cust_h, json={
        "reason": "size_issue", "items": [{"order_item_id": paid_order["items"][0]["id"], "quantity": 1}]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "return_window_closed"


def test_return_quantity_and_ownership_validated(client, db, cust_h, admin_h, paid_order, users):
    from app.tests.conftest import headers_for

    oid = paid_order["id"]
    _deliver(client, admin_h, oid)
    item_id = paid_order["items"][0]["id"]
    too_many = client.post(f"{API}/orders/{oid}/returns", headers=cust_h,
                           json={"reason": "size_issue", "items": [{"order_item_id": item_id, "quantity": 3}]})
    assert too_many.status_code == 422
    other = client.post(f"{API}/orders/{oid}/returns", headers=headers_for(users.customer2),
                        json={"reason": "size_issue", "items": [{"order_item_id": item_id, "quantity": 1}]})
    assert other.status_code == 403


def test_return_not_allowed_before_delivery(client, cust_h, paid_order):
    r = client.post(f"{API}/orders/{paid_order['id']}/returns", headers=cust_h, json={
        "reason": "size_issue", "items": [{"order_item_id": paid_order["items"][0]["id"], "quantity": 1}]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_returnable"


# ----------------------------------------------------------------------------- admin refunds
def test_partial_refund_then_full_remaining(client, db, admin_h, paid_order):
    oid = paid_order["id"]
    r = client.post(f"{ADMIN}/orders/{oid}/refunds", json={"amount": "250.50", "reason": "Late delivery goodwill"}, headers=admin_h)
    assert r.status_code == 201, r.text
    assert r.json()["totals"]["refunded_total"] == "250.50"
    o = _order(db, oid)
    assert o.payment_status == "partially_refunded"
    assert o.status == "payment_confirmed"

    r = client.post(f"{ADMIN}/orders/{oid}/refunds", json={"reason": "Full refund of the rest"}, headers=admin_h)
    assert r.status_code == 201, r.text
    o = _order(db, oid)
    assert o.refunded_total == Decimal("1798.00")
    assert o.payment_status == "refunded"
    amounts = sorted(r.amount_paise for r in db.scalars(select(Refund).where(Refund.order_id == oid)))
    assert amounts == [25050, 154750]

    r = client.post(f"{ADMIN}/orders/{oid}/refunds", json={"amount": "1.00", "reason": "one more"}, headers=admin_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_paid"


def test_refund_over_remaining_amount_rejected(client, db, admin_h, paid_order):
    oid = paid_order["id"]
    client.post(f"{ADMIN}/orders/{oid}/refunds", json={"amount": "1000.00", "reason": "partial"}, headers=admin_h)
    r = client.post(f"{ADMIN}/orders/{oid}/refunds", json={"amount": "798.01", "reason": "too much"}, headers=admin_h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "refund_exceeds_paid"
    assert _order(db, oid).refunded_total == Decimal("1000.00")
    assert client.post(f"{ADMIN}/orders/{oid}/refunds", json={"amount": "0", "reason": "zero"}, headers=admin_h).status_code == 422


def test_refund_on_unpaid_order_rejected(client, catalog, cust_h, admin_h):
    unpaid = place_order(client, cust_h, [(catalog.vid(GLD), 1)])
    r = client.post(f"{ADMIN}/orders/{unpaid['id']}/refunds", json={"reason": "nope"}, headers=admin_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_paid"


def test_refund_idempotency_key_prevents_duplicates(client, db, gateway, users, paid_order):
    o = _order(db, paid_order["id"])
    first = payment_service.refund_order(db, o, amount=Decimal("100.00"), reason="goodwill", actor=users.admin,
                                         idempotency_key="ticket-42")
    db.commit()
    o = _order(db, paid_order["id"])
    second = payment_service.refund_order(db, o, amount=Decimal("100.00"), reason="goodwill", actor=users.admin,
                                          idempotency_key="ticket-42")
    db.commit()
    assert first.id == second.id
    assert db.scalar(select(func.count(Refund.id))) == 1
    o = _order(db, paid_order["id"])
    assert o.refunded_total == Decimal("100.00")
    assert o.payments[0].amount_refunded_paise == 10000
    assert len(gateway._refunds_by_key) == 1


# ----------------------------------------------------------------------------- audit
def test_admin_actions_are_audited(client, db, users, admin_h, paid_order):
    oid = paid_order["id"]
    _status(client, admin_h, oid, "processing")
    sid = _ship(client, admin_h, oid)["shipments"][0]["id"]
    _shipment_status(client, admin_h, sid, "out_for_delivery")
    client.post(f"{ADMIN}/orders/{oid}/refunds", json={"amount": "10.00", "reason": "goodwill"}, headers=admin_h)
    db.expire_all()
    logs = db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
    actions = [a.action for a in logs]
    assert actions == ["order.status", "order.shipment", "shipment.status", "order.refund"]
    assert all(a.actor_id == users.admin.id and a.actor_email == users.admin.email for a in logs)
    assert logs[0].changes == {"from": "payment_confirmed", "to": "processing", "note": None}
    assert logs[0].entity_type == "order" and logs[0].entity_id == str(oid)
    assert logs[-1].changes["amount_paise"] == 1000

    listing = client.get(f"{ADMIN}/audit-logs", headers=admin_h).json()
    assert listing["total"] == 4
