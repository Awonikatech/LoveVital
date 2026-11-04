"""Admin catalogue management, CSV import/export, image uploads, coupons, reports and customers."""
import csv
import io
import os
import struct
import zlib

import pytest
from sqlalchemy import select

from app.api.v1.admin import products as admin_products
from app.models import Product, ProductVariant, RefreshToken
from app.tests.conftest import PASSWORD, inv, pay_order, place_order

ADMIN = "/api/v1/admin"


def _product_body(catalog, **over) -> dict:
    body = {
        "name": "Pearl Drop Earrings", "sku": "JW-EAR-900", "product_type": "jewellery", "category_id": catalog.cats["earrings"].id,
        "tax_rate_id": catalog.tax.id, "status": "active", "short_description": "Freshwater-look pearl drops",
        "variants": [
            {"sku": "JW-EAR-900-WHT", "name": "White", "mrp": "799.00", "sale_price": "649.00", "cost_price": "200.00", "stock": 7,
             "attribute_value_ids": [catalog.attrs["gold"].id]},
            {"sku": "JW-EAR-900-PNK", "name": "Pink", "mrp": "799.00", "sale_price": "599.00", "stock": 0},
        ],
    }
    body.update(over)
    return body


def _png_bytes() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"\x00\xff\x00\x00"  # one red pixel, filter byte 0
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


@pytest.fixture
def media_tmp(tmp_path, monkeypatch):
    """Write uploads into a temp dir instead of the repo's media folder."""
    monkeypatch.setattr(admin_products, "BASE_DIR", str(tmp_path))
    return tmp_path


# ----------------------------------------------------------------------------- products
def test_create_product_with_variants(client, db, catalog, admin_h):
    r = client.post(f"{ADMIN}/products", json=_product_body(catalog), headers=admin_h)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["slug"] == "pearl-drop-earrings"
    assert p["price_min"] == "599.00" and p["mrp_min"] == "799.00" and p["max_discount_pct"] == 25
    v = {x["sku"]: x for x in p["variants"]}
    assert v["JW-EAR-900-WHT"]["on_hand"] == 7 and v["JW-EAR-900-PNK"]["on_hand"] == 0
    assert v["JW-EAR-900-WHT"]["cost_price"] == "200.00"
    assert v["JW-EAR-900-WHT"]["is_default"] is True
    assert p["total_stock"] == 7

    # visible on the storefront and searchable
    assert client.get("/api/v1/products/pearl-drop-earrings").status_code == 200
    assert [x["slug"] for x in client.get("/api/v1/products", params={"q": "pearl"}).json()["items"]] == ["pearl-drop-earrings"]


def test_create_product_validation(client, catalog, admin_h):
    bad = _product_body(catalog)
    bad["variants"][0]["sale_price"] = "899.00"  # > mrp 799
    r = client.post(f"{ADMIN}/products", json=bad, headers=admin_h)
    assert r.status_code == 422
    assert "sale price cannot exceed MRP" in r.json()["error"]["message"]

    dupe_variant = _product_body(catalog)
    dupe_variant["variants"][1]["sku"] = "JW-EAR-001-GLD"  # belongs to the jhumka
    r = client.post(f"{ADMIN}/products", json=dupe_variant, headers=admin_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_sku"

    r = client.post(f"{ADMIN}/products", json=_product_body(catalog, sku="JW-NCK-001"), headers=admin_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_sku"

    same_twice = _product_body(catalog)
    same_twice["variants"][1]["sku"] = "jw-ear-900-wht"
    assert client.post(f"{ADMIN}/products", json=same_twice, headers=admin_h).status_code == 422

    assert client.post(f"{ADMIN}/products", json=_product_body(catalog, variants=[]), headers=admin_h).status_code == 422


def test_failed_create_leaves_no_partial_product(client, db, catalog, admin_h):
    body = _product_body(catalog)
    body["variants"][1]["sku"] = "JW-EAR-001-GLD"
    client.post(f"{ADMIN}/products", json=body, headers=admin_h)
    db.expire_all()
    assert db.scalar(select(Product).where(Product.sku == "JW-EAR-900")) is None


def test_update_variants(client, db, catalog, admin_h):
    p = client.post(f"{ADMIN}/products", json=_product_body(catalog), headers=admin_h).json()
    white = next(v for v in p["variants"] if v["sku"] == "JW-EAR-900-WHT")
    body = _product_body(catalog, name="Pearl Drop Earrings II")
    body["variants"] = [
        {"id": white["id"], "sku": "JW-EAR-900-WHT", "name": "Ivory", "mrp": "899.00", "sale_price": "699.00"},
        {"sku": "JW-EAR-900-BLK", "name": "Black", "mrp": "899.00", "sale_price": "749.00", "stock": 2},
    ]
    r = client.put(f"{ADMIN}/products/{p['id']}", json=body, headers=admin_h)
    assert r.status_code == 200, r.text
    out = r.json()
    skus = {v["sku"]: v for v in out["variants"]}
    assert set(skus) == {"JW-EAR-900-WHT", "JW-EAR-900-BLK"}  # unused pink variant removed
    assert skus["JW-EAR-900-WHT"]["name"] == "Ivory" and skus["JW-EAR-900-WHT"]["on_hand"] == 7
    assert skus["JW-EAR-900-WHT"]["cost_price"] is None  # not supplied -> cleared for admin
    assert out["price_min"] == "699.00"
    assert out["name"] == "Pearl Drop Earrings II"

    body["variants"][0]["id"] = catalog.vid("JW-NCK-001")
    r = client.put(f"{ADMIN}/products/{p['id']}", json=body, headers=admin_h)
    assert r.status_code in (409, 422)


def test_staff_update_does_not_wipe_cost_price(client, db, catalog, staff_h):
    jh = catalog.products["jhumka"]
    body = {
        "name": jh.name, "sku": jh.sku, "product_type": "jewellery", "category_id": jh.category_id, "status": "active",
        "variants": [{"id": v.id, "sku": v.sku, "name": v.name, "mrp": str(v.mrp), "sale_price": str(v.sale_price)} for v in jh.variants],
    }
    r = client.put(f"{ADMIN}/products/{jh.id}", json=body, headers=staff_h)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert str(db.get(ProductVariant, catalog.vid("JW-EAR-001-GLD")).cost_price) == "300.00"


def test_delete_product_with_orders_archives_it(client, db, catalog, cust_h, admin_h):
    place_order(client, cust_h, [(catalog.vid("JW-NCK-001"), 1)], payment_method="cod")
    pid = catalog.products["choker"].id
    r = client.delete(f"{ADMIN}/products/{pid}", headers=admin_h)
    assert r.status_code == 200
    assert r.json()["archived"] is True
    db.expire_all()
    p = db.get(Product, pid)
    assert p.status == "archived" and p.archived_at is not None
    assert client.get("/api/v1/products/kundan-choker-necklace").status_code == 404


def test_delete_product_without_orders(client, db, catalog, admin_h):
    pid = catalog.products["ring"].id
    r = client.delete(f"{ADMIN}/products/{pid}", headers=admin_h)
    assert r.json() == {"deleted": True}
    db.expire_all()
    assert db.get(Product, pid) is None


# ----------------------------------------------------------------------------- CSV
def test_csv_export(client, catalog, admin_h):
    r = client.get(f"{ADMIN}/products-export.csv", headers=admin_h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert list(rows[0].keys())[:2] == ["product_sku", "product_name"]
    skus = {row["variant_sku"] for row in rows}
    assert {"JW-EAR-001-GLD", "JW-EAR-001-RED", "JW-NCK-001", "AP-KRT-001-S"} <= skus
    gold = next(row for row in rows if row["variant_sku"] == "JW-EAR-001-GLD")
    assert gold["stock"] == "10" and gold["cost_price"] == "300.00" and gold["category_slug"] == "earrings"


CSV_HEADER = "product_sku,product_name,product_type,category_slug,status,variant_sku,variant_name,mrp,sale_price,stock,attributes\n"


def _upload_csv(client, admin_h, text: str, dry_run: bool):
    return client.post(f"{ADMIN}/products-import", params={"dry_run": str(dry_run).lower()}, headers=admin_h,
                       files={"file": ("products.csv", text.encode(), "text/csv")})


def test_csv_import_dry_run_does_not_persist(client, db, catalog, admin_h):
    text = CSV_HEADER + "JW-NEW-1,Moonstone Ring,jewellery,rings,active,JW-NEW-1-S,Silver,600.00,450.00,8,color=Silver\n"
    r = _upload_csv(client, admin_h, text, dry_run=True)
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 1, "updated": 0, "errors": [], "dry_run": True}
    db.expire_all()
    assert db.scalar(select(Product).where(Product.sku == "JW-NEW-1")) is None


def test_csv_import_creates_and_updates(client, db, catalog, admin_h):
    text = CSV_HEADER + (
        "JW-NEW-1,Moonstone Ring,jewellery,rings,active,JW-NEW-1-S,Silver,600.00,450.00,8,color=Silver\n"
        "JW-EAR-001,Temple Jhumka Earrings,jewellery,earrings,active,JW-EAR-001-GLD,Gold,1299.00,849.00,15,\n"
        "JW-BAD-1,Broken Row,jewellery,no-such-category,active,JW-BAD-1,X,100.00,90.00,1,\n"
        "JW-BAD-2,Pricey,jewellery,rings,active,JW-BAD-2,X,100.00,190.00,1,\n"
    )
    r = _upload_csv(client, admin_h, text, dry_run=False)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1 and body["updated"] == 1
    assert [e["line"] for e in body["errors"]] == [4, 5]
    db.expire_all()
    new = db.scalar(select(Product).where(Product.sku == "JW-NEW-1"))
    assert new.status == "active" and str(new.price_min) == "450.00"
    assert new.variants[0].attribute_values[0].value == "Silver"
    assert inv(db, new.variants[0].id).quantity_on_hand == 8
    gold = db.get(ProductVariant, catalog.vid("JW-EAR-001-GLD"))
    assert str(gold.sale_price) == "849.00"
    assert inv(db, gold.id).quantity_on_hand == 15
    assert db.scalar(select(Product).where(Product.sku == "JW-BAD-1")) is None


def test_csv_import_missing_columns(client, catalog, admin_h):
    r = _upload_csv(client, admin_h, "product_sku,product_name\nX,Y\n", dry_run=False)
    assert r.status_code == 422 and "Missing columns" in r.json()["error"]["message"]


# ----------------------------------------------------------------------------- uploads
def test_image_upload_accepts_real_png(client, db, catalog, admin_h, media_tmp):
    pid = catalog.products["ring"].id
    r = client.post(f"{ADMIN}/products/{pid}/images", headers=admin_h, files={"file": ("x.png", _png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert url.startswith("/media/uploads/products/") and url.endswith(".png")
    assert r.json()["is_primary"] is True
    assert os.path.exists(os.path.join(media_tmp, url.lstrip("/")))


def test_image_upload_rejects_disguised_text_file(client, catalog, admin_h, media_tmp):
    pid = catalog.products["ring"].id
    r = client.post(f"{ADMIN}/products/{pid}/images", headers=admin_h,
                    files={"file": ("evil.png", b"<?php system($_GET['c']); ?>", "image/png")})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_file_type"
    r = client.post(f"{ADMIN}/products/{pid}/images", headers=admin_h, files={"file": ("a.svg", b"<svg/>", "image/svg+xml")})
    assert r.status_code == 422
    assert not any(media_tmp.rglob("*.*"))


def test_image_upload_rejects_oversize(client, catalog, admin_h, media_tmp, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    big = _png_bytes() + b"\x00" * (1024 * 1024)
    r = client.post(f"{ADMIN}/products/{catalog.products['ring'].id}/images", headers=admin_h,
                    files={"file": ("big.png", big, "image/png")})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "file_too_large"


# ----------------------------------------------------------------------------- coupons
COUPON = {"code": "diwali20", "discount_type": "percent", "value": "20", "max_discount": "500", "min_cart_value": "999"}


def test_coupon_crud(client, catalog, admin_h, staff_h):
    r = client.post(f"{ADMIN}/coupons", json=COUPON, headers=admin_h)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["code"] == "DIWALI20" and c["value"] == "20.00" and c["max_discount"] == "500.00"

    assert client.post(f"{ADMIN}/coupons", json=COUPON, headers=admin_h).status_code == 409
    assert client.post(f"{ADMIN}/coupons", json={**COUPON, "code": "STAFFX"}, headers=staff_h).status_code == 403

    r = client.put(f"{ADMIN}/coupons/{c['id']}", json={**COUPON, "value": "25"}, headers=admin_h)
    assert r.status_code == 200 and r.json()["value"] == "25.00"
    listing = client.get(f"{ADMIN}/coupons", headers=staff_h)
    assert listing.status_code == 200 and listing.json()[0]["code"] == "DIWALI20"

    assert client.delete(f"{ADMIN}/coupons/{c['id']}", headers=admin_h).json()["message"] == "Coupon deleted."
    assert client.get(f"{ADMIN}/coupons", headers=admin_h).json() == []


@pytest.mark.parametrize("override", [
    {"value": "95"},                                      # percent > 90
    {"value": "0"},                                       # percent 0
    {"discount_type": "fixed", "value": "0"},             # fixed must be positive
    {"applies_to": "categories"},                         # needs category ids
    {"code": "bad code!"},                                # invalid characters
    {"starts_at": "2026-10-10T00:00:00", "ends_at": "2026-10-01T00:00:00"},
])
def test_coupon_validation(client, catalog, admin_h, override):
    r = client.post(f"{ADMIN}/coupons", json={**COUPON, **override}, headers=admin_h)
    assert r.status_code == 422, r.text


def test_used_coupon_is_deactivated_not_deleted(client, catalog, users, cust_h, admin_h):
    c = client.post(f"{ADMIN}/coupons", json={**COUPON, "min_cart_value": "0"}, headers=admin_h).json()
    place_order(client, cust_h, [(catalog.vid("JW-NCK-001"), 1)], payment_method="cod", coupon_code="DIWALI20")
    r = client.delete(f"{ADMIN}/coupons/{c['id']}", headers=admin_h)
    assert "deactivated" in r.json()["message"]
    assert client.get(f"{ADMIN}/coupons/{c['id']}/redemptions", headers=admin_h).json()[0]["discount_amount"] == "399.80"


# ----------------------------------------------------------------------------- reports
REPORT_NAMES = ["sales", "order_status", "products", "categories", "inventory", "coupons", "customers", "refunds"]


@pytest.fixture
def some_orders(client, catalog, users, cust_h):
    pay_order(client, cust_h, place_order(client, cust_h, [(catalog.vid("JW-EAR-001-GLD"), 2)]))
    place_order(client, cust_h, [(catalog.vid("AP-KRT-001-S"), 1)], payment_method="cod")


def test_dashboard_for_admin(client, admin_h, some_orders):
    r = client.get(f"{ADMIN}/dashboard", headers=admin_h)
    assert r.status_code == 200
    d = r.json()
    assert d["summary"]["orders"] == 2
    assert d["summary"]["revenue"] == "2525.00"  # 1798 prepaid + (599 + 79 shipping + 49 COD fee)
    assert d["queues"]["pending_orders"] == 2
    assert len(d["recent_orders"]) == 2


@pytest.mark.parametrize("name", REPORT_NAMES)
def test_every_report_json_and_csv(client, admin_h, some_orders, name):
    r = client.get(f"{ADMIN}/reports/{name}", headers=admin_h)
    assert r.status_code == 200, r.text
    assert r.json()["report"] == name
    c = client.get(f"{ADMIN}/reports/{name}", params={"format": "csv"}, headers=admin_h)
    assert c.status_code == 200
    assert c.headers["content-type"].startswith("text/csv")
    assert f"{name}-report-" in c.headers["content-disposition"]


@pytest.mark.parametrize("granularity", ["week", "month", "year"])
def test_sales_report_granularity(client, admin_h, some_orders, granularity):
    r = client.get(f"{ADMIN}/reports/sales", params={"granularity": granularity}, headers=admin_h)
    assert r.status_code == 200
    assert sum(row["orders"] for row in r.json()["data"]["series"]) == 2


def test_sales_report_csv_rows(client, admin_h, some_orders):
    c = client.get(f"{ADMIN}/reports/products", params={"format": "csv"}, headers=admin_h).text
    rows = list(csv.DictReader(io.StringIO(c)))
    assert {r["sku"] for r in rows} == {"JW-EAR-001", "AP-KRT-001"}


def test_unknown_report_rejected(client, admin_h):
    assert client.get(f"{ADMIN}/reports/secret", headers=admin_h).status_code == 422


def test_orders_csv_export(client, admin_h, some_orders):
    r = client.get(f"{ADMIN}/orders-export.csv", headers=admin_h)
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 2 and {r["payment_method"] for r in rows} == {"razorpay", "cod"}


# ----------------------------------------------------------------------------- customers
def test_disable_customer_requires_reason_and_revokes_sessions(client, db, users, admin_h, staff_h):
    login = client.post("/api/v1/auth/login", json={"email": users.customer.email, "password": PASSWORD})
    refresh, csrf = login.cookies["swk_refresh"], login.cookies["swk_csrf"]
    uid = users.customer.id

    r = client.patch(f"{ADMIN}/customers/{uid}", json={"is_active": False}, headers=admin_h)
    assert r.status_code == 422 and "reason" in r.json()["error"]["message"]
    r = client.patch(f"{ADMIN}/customers/{uid}", json={"is_active": False, "disabled_reason": "Fraud"}, headers=staff_h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "forbidden"

    r = client.patch(f"{ADMIN}/customers/{uid}", json={"is_active": False, "disabled_reason": "Chargeback fraud"}, headers=admin_h)
    assert r.status_code == 200 and r.json() == {"ok": True, "is_active": False}
    db.expire_all()
    tokens = db.scalars(select(RefreshToken).where(RefreshToken.user_id == uid)).all()
    assert tokens and all(t.revoked_at is not None for t in tokens)

    client.cookies.clear()
    r = client.post("/api/v1/auth/refresh", headers={"Cookie": f"swk_refresh={refresh}; swk_csrf={csrf}", "X-CSRF-Token": csrf})
    assert r.status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": users.customer.email, "password": PASSWORD}).status_code == 403

    detail = client.get(f"{ADMIN}/customers/{uid}", headers=admin_h).json()
    assert detail["is_active"] is False and detail["disabled_reason"] == "Chargeback fraud"


def test_admin_cannot_disable_self(client, users, admin_h):
    r = client.patch(f"{ADMIN}/customers/{users.admin.id}", json={"is_active": False, "disabled_reason": "x"}, headers=admin_h)
    assert r.status_code == 422


def test_customer_list(client, users, admin_h, some_orders):
    data = client.get(f"{ADMIN}/customers", params={"sort": "spend"}, headers=admin_h).json()
    assert data["total"] == 2
    assert data["items"][0]["email"] == users.customer.email
    assert data["items"][0]["orders"] == 2
