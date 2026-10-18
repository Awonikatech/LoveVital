"""Role/permission enforcement and order ownership."""
from app.tests.conftest import GUEST_ADDRESS, checkout, guest_cart, headers_for, pay_order, place_order, add_to_cart


def test_customer_forbidden_from_admin(client, cust_h):
    r = client.get("/api/v1/admin/dashboard", headers=cust_h)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_anonymous_unauthorized_on_admin(client, users):
    assert client.get("/api/v1/admin/dashboard").status_code == 401
    assert client.get("/api/v1/admin/orders").status_code == 401


def test_staff_dashboard_hides_finance(client, staff_h, admin_h):
    staff = client.get("/api/v1/admin/dashboard", headers=staff_h)
    assert staff.status_code == 200, staff.text
    data = staff.json()
    assert data["finance_visible"] is False
    assert "revenue" not in data["summary"] and "gross_sales" not in data["summary"]
    assert all(set(row) == {"period", "orders"} for row in data["sales_trend"])

    admin = client.get("/api/v1/admin/dashboard", headers=admin_h).json()
    assert admin["finance_visible"] is True
    assert "revenue" in admin["summary"] and "gross_margin" in admin["summary"]


def test_staff_cannot_view_sales_report(client, staff_h):
    r = client.get("/api/v1/admin/reports/sales", headers=staff_h)
    assert r.status_code == 403


def test_staff_cannot_refund(client, catalog, users, staff_h, cust_h):
    order = pay_order(client, cust_h, place_order(client, cust_h, [(catalog.vid("JW-EAR-001-GLD"), 1)]))
    r = client.post(f"/api/v1/admin/orders/{order['id']}/refunds", json={"reason": "goodwill"}, headers=staff_h)
    assert r.status_code == 403
    assert "refunds:write" in r.json()["error"]["message"]


def test_staff_cannot_cancel_paid_order(client, catalog, users, staff_h, cust_h):
    order = pay_order(client, cust_h, place_order(client, cust_h, [(catalog.vid("JW-EAR-001-GLD"), 1)]))
    r = client.post(f"/api/v1/admin/orders/{order['id']}/cancel", json={"reason": "test"}, headers=staff_h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "refund_permission_required"


def test_cost_price_visible_to_admin_only(client, catalog, staff_h, admin_h):
    pid = catalog.products["jhumka"].id
    staff_view = client.get(f"/api/v1/admin/products/{pid}", headers=staff_h).json()
    admin_view = client.get(f"/api/v1/admin/products/{pid}", headers=admin_h).json()
    assert all("cost_price" not in v and "margin_pct" not in v for v in staff_view["variants"])
    assert admin_view["variants"][0]["cost_price"] == "300.00"
    assert client.get("/api/v1/admin/products/meta", headers=staff_h).json()["can_view_cost"] is False

    export = client.get("/api/v1/admin/products-export.csv", headers=staff_h).text
    assert "300.00" not in export


def test_cost_price_never_on_storefront(client, catalog):
    body = client.get(f"/api/v1/products/{catalog.products['jhumka'].slug}").text
    assert "cost" not in body


def test_customer_cannot_read_another_customers_order(client, catalog, users, cust_h):
    order = place_order(client, cust_h, [(catalog.vid("JW-EAR-001-GLD"), 1)])
    other = headers_for(users.customer2)
    for ref in (str(order["id"]), order["order_number"]):
        r = client.get(f"/api/v1/orders/{ref}", headers=other)
        assert r.status_code in (403, 404)
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", json={"reason": "not mine"}, headers=other)
    assert r.status_code in (403, 404)
    assert client.get(f"/api/v1/orders/{order['id']}", headers=cust_h).status_code == 200
    assert client.get("/api/v1/orders", headers=other).json()["total"] == 0


def test_guest_order_requires_correct_order_key(client, catalog):
    guest = guest_cart(client)
    add_to_cart(client, guest, catalog.vid("JW-EAR-001-GLD"))
    order = checkout(client, guest, email="guest@example.com", address=GUEST_ADDRESS)["order"]
    key = order["order_key"]

    assert client.get(f"/api/v1/orders/{order['id']}").status_code == 404
    assert client.get(f"/api/v1/orders/{order['id']}", params={"key": "0" * 32}).status_code == 403
    ok = client.get(f"/api/v1/orders/{order['order_number']}", params={"key": key})
    assert ok.status_code == 200
    assert ok.json()["order_number"] == order["order_number"]

    # paying also needs the key
    assert client.post("/api/v1/payments/razorpay/create-order", json={"order_id": str(order["id"])}).status_code == 404
    assert client.post("/api/v1/payments/razorpay/create-order",
                       json={"order_id": str(order["id"]), "order_key": key}).status_code == 200


def test_guest_lookup_requires_matching_email(client, catalog):
    guest = guest_cart(client)
    add_to_cart(client, guest, catalog.vid("JW-EAR-001-GLD"))
    order = checkout(client, guest, email="guest@example.com", payment_method="cod", address=GUEST_ADDRESS)["order"]
    bad = client.post("/api/v1/orders/lookup", json={"order_number": order["order_number"], "email": "other@example.com"})
    assert bad.status_code == 404
    good = client.post("/api/v1/orders/lookup", json={"order_number": order["order_number"], "email": "GUEST@example.com"})
    assert good.status_code == 200
    assert good.json()["order_key"] == order["order_key"]
