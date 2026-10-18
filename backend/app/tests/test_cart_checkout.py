"""Cart lifecycle, coupons and checkout (server-side totals, idempotency, inventory effects)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.database import utcnow
from app.models import Coupon, InventoryMovement, InventoryReservation, Order
from app.tests.conftest import ADDRESS, add_to_cart, checkout, guest_cart, headers_for, inv, login, place_order

API = "/api/v1"


@pytest.fixture
def coupons(db, catalog):
    now = utcnow()
    rows = {
        "SAVE10": Coupon(code="SAVE10", discount_type="percent", value=Decimal("10"), usage_limit_per_user=None),
        "OLD25": Coupon(code="OLD25", discount_type="percent", value=Decimal("25"), starts_at=now - timedelta(days=30),
                        ends_at=now - timedelta(days=1)),
        "ONCE": Coupon(code="ONCE", discount_type="fixed", value=Decimal("100"), usage_limit_per_user=1),
        "WELCOME": Coupon(code="WELCOME", discount_type="percent", value=Decimal("15"), first_order_only=True),
        "BIG": Coupon(code="BIG", discount_type="fixed", value=Decimal("200"), min_cart_value=Decimal("5000")),
    }
    db.add_all(rows.values())
    db.commit()
    return rows


# ----------------------------------------------------------------------------- cart
def test_guest_cart_add_update_remove(client, catalog):
    h = guest_cart(client)
    cart = add_to_cart(client, h, catalog.vid("JW-EAR-001-GLD"), 2)
    assert cart["item_count"] == 2
    item = cart["items"][0]
    assert item["unit_price"] == "899.00" and item["line_subtotal"] == "1798.00"
    assert cart["totals"]["grand_total"] == "1798.00"  # free shipping above 999
    assert cart["can_checkout"] is True

    # adding the same variant again increments
    cart = add_to_cart(client, h, catalog.vid("JW-EAR-001-GLD"), 1)
    assert len(cart["items"]) == 1 and cart["items"][0]["quantity"] == 3

    r = client.patch(f"{API}/cart/items/{item['id']}", json={"quantity": 1}, headers=h)
    assert r.status_code == 200
    assert r.json()["totals"]["shipping_charge"] == "79.00"
    assert r.json()["totals"]["amount_to_free_shipping"] == "100.00"

    r = client.delete(f"{API}/cart/items/{item['id']}", headers=h)
    assert r.status_code == 200 and r.json()["items"] == []

    # another guest cannot see this cart
    assert client.get(f"{API}/cart").json()["token"] != h["X-Cart-Token"]


def test_quantity_above_stock_rejected(client, catalog):
    h = guest_cart(client)
    r = client.post(f"{API}/cart/items", json={"variant_id": catalog.vid("JW-EAR-001-RED"), "quantity": 4}, headers=h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "insufficient_stock"
    assert r.json()["error"]["details"] == {"available": 3}

    add_to_cart(client, h, catalog.vid("JW-EAR-001-RED"), 3)
    item_id = client.get(f"{API}/cart", headers=h).json()["items"][0]["id"]
    r = client.patch(f"{API}/cart/items/{item_id}", json={"quantity": 4}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "insufficient_stock"


def test_out_of_stock_and_archived_items_rejected(client, catalog):
    h = guest_cart(client)
    r = client.post(f"{API}/cart/items", json={"variant_id": catalog.vid("JW-RNG-001"), "quantity": 1}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "out_of_stock"
    r = client.post(f"{API}/cart/items", json={"variant_id": catalog.vid("JW-BRC-OLD"), "quantity": 1}, headers=h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "variant_unavailable"


def test_max_order_qty_enforced(client, catalog):
    h = guest_cart(client)
    r = client.post(f"{API}/cart/items", json={"variant_id": catalog.vid("JW-NCK-001"), "quantity": 4}, headers=h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "above_max_qty"
    add_to_cart(client, h, catalog.vid("JW-NCK-001"), 3)
    r = client.post(f"{API}/cart/items", json={"variant_id": catalog.vid("JW-NCK-001"), "quantity": 1}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "above_max_qty"


# ----------------------------------------------------------------------------- coupons
def test_apply_valid_coupon(client, catalog, coupons, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-NCK-001"), 1)
    r = client.post(f"{API}/cart/coupon", json={"code": "save10"}, headers=cust_h)
    assert r.status_code == 200, r.text
    totals = r.json()["totals"]
    assert totals["coupon"] == {"code": "SAVE10", "applied": True, "message": "SAVE10 applied."}
    assert totals["coupon_discount"] == "199.90"
    assert totals["grand_total"] == "1799.10"

    r = client.delete(f"{API}/cart/coupon", headers=cust_h)
    assert r.json()["totals"]["coupon"] is None


def test_expired_and_unknown_coupons_rejected(client, catalog, coupons, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-NCK-001"), 1)
    r = client.post(f"{API}/cart/coupon", json={"code": "OLD25"}, headers=cust_h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "coupon_invalid"
    assert "expired" in r.json()["error"]["message"]
    r = client.post(f"{API}/cart/coupon", json={"code": "NOPE"}, headers=cust_h)
    assert r.status_code == 422 and "not valid" in r.json()["error"]["message"]


def test_coupon_min_cart_value(client, catalog, coupons, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-NCK-001"), 1)
    r = client.post(f"{API}/cart/coupon", json={"code": "BIG"}, headers=cust_h)
    assert r.status_code == 422
    assert "3001.00 more" in r.json()["error"]["message"]


def test_coupon_per_user_limit(client, db, catalog, coupons, users, cust_h):
    order = place_order(client, cust_h, [(catalog.vid("JW-NCK-001"), 1)], payment_method="cod", coupon_code="ONCE")
    assert order["totals"]["coupon_discount"] == "100.00"
    db.expire_all()
    assert db.get(Coupon, coupons["ONCE"].id).times_used == 1

    add_to_cart(client, cust_h, catalog.vid("JW-NCK-001"), 1)
    r = client.post(f"{API}/cart/coupon", json={"code": "ONCE"}, headers=cust_h)
    assert r.status_code == 422
    assert "already used" in r.json()["error"]["message"]
    # but another customer can still use it
    other = headers_for(users.customer2)
    add_to_cart(client, other, catalog.vid("JW-NCK-001"), 1)
    assert client.post(f"{API}/cart/coupon", json={"code": "ONCE"}, headers=other).status_code == 200


def test_first_order_only_coupon(client, catalog, coupons, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-GLD"), 1)
    assert client.post(f"{API}/cart/coupon", json={"code": "WELCOME"}, headers=cust_h).status_code == 200
    client.delete(f"{API}/cart/coupon", headers=cust_h)
    checkout(client, cust_h, payment_method="cod")

    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-GLD"), 1)
    r = client.post(f"{API}/cart/coupon", json={"code": "WELCOME"}, headers=cust_h)
    assert r.status_code == 422
    assert "first order" in r.json()["error"]["message"]


def test_checkout_with_invalid_coupon_rejected(client, catalog, coupons, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-GLD"), 1)
    r = checkout(client, cust_h, coupon_code="OLD25", expect=422)
    assert r["error"]["code"] == "coupon_invalid"


# ----------------------------------------------------------------------------- checkout
def test_checkout_totals_are_computed_server_side(client, db, catalog, coupons, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-GLD"), 1)
    tampered = {"grand_total": "1.00", "subtotal": "1.00", "shipping_charge": "0.00", "coupon_discount": "898.00",
                "items": [{"variant_id": catalog.vid("JW-EAR-001-GLD"), "unit_price": "1.00"}]}
    order = checkout(client, cust_h, coupon_code="SAVE10", **tampered)["order"]
    t = order["totals"]
    assert t["subtotal"] == "899.00"
    assert t["coupon_discount"] == "89.90"
    assert t["shipping_charge"] == "79.00"
    assert t["grand_total"] == "888.10"
    assert t["tax_total"] == "23.57"  # 3% GST inside 809.10
    assert order["items"][0]["unit_price"] == "899.00"
    db.expire_all()
    stored = db.scalar(select(Order).where(Order.id == order["id"]))
    assert stored.grand_total == Decimal("888.10")


def test_checkout_idempotency_key(client, db, catalog, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-GLD"), 2)
    first = checkout(client, cust_h, idempotency_key="key-123")
    second = checkout(client, cust_h, idempotency_key="key-123")
    assert first["created"] is True and second["created"] is False
    assert first["order"]["id"] == second["order"]["id"]
    assert db.scalar(select(func.count(Order.id))) == 1
    assert inv(db, catalog.vid("JW-EAR-001-GLD")).quantity_reserved == 2


def test_idempotency_key_is_scoped_per_user(client, db, catalog, users, cust_h):
    other = headers_for(users.customer2)
    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-GLD"), 1)
    add_to_cart(client, other, catalog.vid("JW-EAR-001-GLD"), 1)
    a = checkout(client, cust_h, idempotency_key="same-key")["order"]
    b = checkout(client, other, idempotency_key="same-key")["order"]
    assert a["id"] != b["id"]


def test_insufficient_stock_at_checkout_conflicts(client, db, catalog, users, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-RED"), 3)
    # someone else reserves 2 of the 3 units first
    place_order(client, headers_for(users.customer2), [(catalog.vid("JW-EAR-001-RED"), 2)])
    r = checkout(client, cust_h, expect=409)
    assert r["error"]["code"] == "cart_invalid"
    assert any(i["code"] == "insufficient_stock" for i in r["error"]["details"])
    assert db.scalar(select(func.count(Order.id))) == 1
    assert inv(db, catalog.vid("JW-EAR-001-RED")).quantity_reserved == 2


def test_cod_checkout_commits_inventory(client, db, catalog, cust_h):
    vid = catalog.vid("JW-EAR-001-GLD")
    order = place_order(client, cust_h, [(vid, 2)], payment_method="cod")
    assert order["status"] == "order_placed"
    assert order["totals"]["cod_charge"] == "49.00"
    assert order["totals"]["grand_total"] == "1847.00"  # 1798 + 49 COD, free shipping
    i = inv(db, vid)
    assert (i.quantity_on_hand, i.quantity_reserved) == (8, 0)
    mv = db.scalars(select(InventoryMovement).where(InventoryMovement.variant_id == vid).order_by(InventoryMovement.id)).all()
    assert mv[-1].movement_type == "sale" and mv[-1].quantity == -2 and mv[-1].balance_after == 8
    assert mv[-1].reference_id == order["order_number"]
    resv = db.scalar(select(InventoryReservation).where(InventoryReservation.order_id == order["id"]))
    assert resv.status == "committed"


def test_razorpay_checkout_reserves_stock(client, db, catalog, cust_h):
    vid = catalog.vid("JW-EAR-001-GLD")
    order = place_order(client, cust_h, [(vid, 2)])
    assert order["status"] == "payment_pending" and order["payment_status"] == "pending"
    assert order["can_pay"] is True
    i = inv(db, vid)
    assert (i.quantity_on_hand, i.quantity_reserved, i.available) == (10, 2, 8)
    resv = db.scalar(select(InventoryReservation).where(InventoryReservation.order_id == order["id"]))
    assert resv.status == "active" and resv.quantity == 2 and resv.expires_at > utcnow()
    # the cart was converted; the customer's next cart is empty
    assert client.get(f"{API}/cart", headers=cust_h).json()["items"] == []


def test_unserviceable_pin_rejected(client, catalog, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-GLD"), 1)
    r = checkout(client, cust_h, address={**ADDRESS, "pin_code": "682551", "state": "Lakshadweep"}, expect=422)
    assert r["error"]["code"] == "pin_not_serviceable"


def test_checkout_requires_email_for_guest_and_non_empty_cart(client, catalog, cust_h):
    h = guest_cart(client)
    add_to_cart(client, h, catalog.vid("JW-EAR-001-GLD"), 1)
    assert checkout(client, h, expect=422)["error"]["code"] == "email_required"
    assert checkout(client, cust_h, expect=422)["error"]["code"] == "empty_cart"


def test_checkout_validate_quote(client, catalog, cust_h):
    add_to_cart(client, cust_h, catalog.vid("JW-EAR-001-GLD"), 1)
    r = client.post(f"{API}/checkout/validate", json={"pin_code": "110017", "payment_method": "cod"}, headers=cust_h)
    assert r.status_code == 200
    q = r.json()
    assert q["cod_available"] is True
    assert q["totals"]["grand_total"] == "1027.00"  # 899 + 79 + 49
    assert q["delivery"]["serviceable"] is True


def test_cart_merges_into_user_cart_on_login(client, db, catalog, users):
    # the customer already has a cart with one item
    cust_h = login(client, users.customer.email)
    add_to_cart(client, cust_h, catalog.vid("AP-KRT-001-S"), 1)

    guest = guest_cart(client)
    add_to_cart(client, guest, catalog.vid("JW-EAR-001-GLD"), 2)
    add_to_cart(client, guest, catalog.vid("AP-KRT-001-S"), 1)

    r = client.post(f"{API}/auth/login", json={"email": users.customer.email, "password": "Passw0rd123"}, headers=guest)
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cart = client.get(f"{API}/cart", headers=h).json()
    qty = {i["sku"]: i["quantity"] for i in cart["items"]}
    assert qty == {"AP-KRT-001-S": 2, "JW-EAR-001-GLD": 2}
    # the guest token no longer resolves to a usable cart
    assert client.get(f"{API}/cart", headers=guest).json()["items"] == []


def test_guest_cart_adopted_when_user_has_no_cart(client, catalog, users):
    guest = guest_cart(client)
    add_to_cart(client, guest, catalog.vid("JW-EAR-001-GLD"), 1)
    r = client.post(f"{API}/auth/login", json={"email": users.customer2.email, "password": "Passw0rd123"}, headers=guest)
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cart = client.get(f"{API}/cart", headers=h).json()
    assert [i["sku"] for i in cart["items"]] == ["JW-EAR-001-GLD"]
