"""Shared fixtures for the backend test suite.

Environment is configured *before* the app is imported so `app.core.config.settings` and the
module-level engine pick up the test configuration (in-memory SQLite with a StaticPool).
Every test gets freshly created tables (create_all / drop_all on the in-memory database).
"""
from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["RAZORPAY_MODE"] = "mock"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["EMAIL_BACKEND"] = "console"
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef-0123456789")

from dataclasses import dataclass, field  # noqa: E402
from decimal import Decimal  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core import security  # noqa: E402

# Argon2id with the library defaults costs ~50-100 ms per hash; tests create many users, so use cheap
# parameters. Hashes are still real Argon2id ("$argon2id$...") and go through the same code paths.
security._ph = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)

from app.core.config import settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.deps import ROLE_PERMISSIONS  # noqa: E402
from app.core.rate_limit import reset_rate_limits  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.integrations import razorpay_gateway  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    Inventory,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    Role,
    ServiceablePinCode,
    ShippingMethod,
    TaxRate,
    User,
)
from app.services import catalog_service, inventory_service, notification_service  # noqa: E402

assert settings.ENVIRONMENT == "test" and settings.DATABASE_URL == "sqlite://", "test settings not applied"

PASSWORD = "Passw0rd123"
ADDRESS = {
    "full_name": "Priya Sharma",
    "phone": "9810012345",
    "line1": "Flat 402, Lotus Residency",
    "city": "New Delhi",
    "state": "Delhi",
    "pin_code": "110001",
}


# ----------------------------------------------------------------------------- global isolation
@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    """Fresh schema, fresh mock gateway, no rate limits, no email threads — for every test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    razorpay_gateway.set_gateway(None)
    reset_rate_limits()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(notification_service, "SYNC_DISPATCH", True)
    yield
    razorpay_gateway.set_gateway(None)
    reset_rate_limits()


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Capture every email the app tries to send (order mails and auth background tasks)."""
    sent: list[dict] = []

    def fake_send(template, to, subject, body, user_id=None):
        sent.append({"template": template, "to": to, "subject": subject, "body": body})

    monkeypatch.setattr(notification_service, "send_email_task", fake_send)
    import app.api.v1.auth as auth_api

    monkeypatch.setattr(auth_api, "send_email_task", fake_send)
    return sent


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def gateway() -> razorpay_gateway.MockRazorpayGateway:
    gw = razorpay_gateway.get_gateway()
    assert isinstance(gw, razorpay_gateway.MockRazorpayGateway)
    return gw


# ----------------------------------------------------------------------------- data builders
def make_roles(db) -> dict[str, Role]:
    roles = {}
    for name, perms in ROLE_PERMISSIONS.items():
        r = db.scalar(select(Role).where(Role.name == name))
        if not r:
            r = Role(name=name, description=name.title(), permissions=list(perms))
            db.add(r)
        roles[name] = r
    db.flush()
    return roles


_HASH_CACHE: dict[str, str] = {}


def make_user(db, email: str, role: str = "customer", password: str = PASSWORD, name: str = "Test User", **kw) -> User:
    roles = make_roles(db)
    if password not in _HASH_CACHE:
        _HASH_CACHE[password] = hash_password(password)
    u = User(email=email.lower(), full_name=name, password_hash=_HASH_CACHE[password], **kw)
    u.roles.append(roles[role])
    db.add(u)
    db.flush()
    return u


def headers_for(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role_names)}"}


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@dataclass
class Catalog:
    tax: TaxRate
    cats: dict[str, Category]
    products: dict[str, Product]
    variants: dict[str, ProductVariant]
    attrs: dict[str, ProductAttributeValue]
    shipping: ShippingMethod
    extra: dict = field(default_factory=dict)

    def vid(self, sku: str) -> int:
        return self.variants[sku].id


def _attr(db, code: str, name: str, axis: bool, value: str, hexv: str | None = None) -> ProductAttributeValue:
    a = db.scalar(select(ProductAttribute).where(ProductAttribute.code == code))
    if not a:
        a = ProductAttribute(code=code, name=name, display_type="swatch" if code == "color" else "button",
                             is_variant_axis=axis, is_filterable=True)
        db.add(a)
        db.flush()
    slug = value.lower().replace(" ", "-")
    av = db.scalar(select(ProductAttributeValue).where(ProductAttributeValue.attribute_id == a.id, ProductAttributeValue.slug == slug))
    if not av:
        av = ProductAttributeValue(attribute_id=a.id, value=value, slug=slug, swatch_hex=hexv)
        db.add(av)
        db.flush()
    return av


def make_product(db, cat: Category, *, sku: str, name: str, product_type: str = "jewellery", tax: TaxRate | None = None,
                 variants: list[dict], status: str = "active", admin: User | None = None, **kw) -> Product:
    from app.core.database import utcnow

    p = Product(sku=sku, slug=name.lower().replace(" ", "-"), name=name, product_type=product_type, category_id=cat.id,
                tax_rate_id=tax.id if tax else None, status=status, published_at=utcnow(), **kw)
    db.add(p)
    db.flush()
    for i, spec in enumerate(variants):
        v = ProductVariant(product=p, sku=spec["sku"], name=spec.get("name", spec["sku"]), mrp=Decimal(spec["mrp"]),
                           sale_price=Decimal(spec["sale"]), cost_price=Decimal(spec["cost"]) if spec.get("cost") else None,
                           is_default=i == 0, display_order=i)
        v.attribute_values = list(spec.get("attrs", []))
        p.variants.append(v)
        db.flush()
        v.inventory = Inventory(variant_id=v.id, quantity_on_hand=0, quantity_reserved=0, low_stock_threshold=2)
        db.flush()
        if spec.get("stock"):
            inventory_service.adjust(db, v.id, spec["stock"], "initial", "Opening stock", admin)
    db.flush()
    db.refresh(p)
    catalog_service.refresh_product_aggregates(db, p)
    db.flush()
    return p


def build_catalog(db) -> Catalog:
    make_roles(db)
    tax = TaxRate(name="GST 3% Jewellery", hsn_code="7117", rate=Decimal("3.00"))
    tax5 = TaxRate(name="GST 5% Apparel", hsn_code="6204", rate=Decimal("5.00"))
    db.add_all([tax, tax5])
    db.flush()

    cats: dict[str, Category] = {}
    for slug, name, parent in [("jewellery", "Jewellery", None), ("earrings", "Earrings", "jewellery"),
                               ("necklaces", "Necklaces", "jewellery"), ("rings", "Rings", "jewellery"),
                               ("apparel", "Apparel", None), ("kurtis", "Kurtis", "apparel")]:
        c = Category(slug=slug, name=name, parent_id=cats[parent].id if parent else None)
        db.add(c)
        db.flush()
        cats[slug] = c

    gold = _attr(db, "color", "Colour", True, "Gold", "#D4AF37")
    red = _attr(db, "color", "Colour", True, "Red", "#B22222")
    blue = _attr(db, "color", "Colour", True, "Blue", "#1F3A93")
    silver = _attr(db, "color", "Colour", True, "Silver", "#C0C0C0")
    size_s = _attr(db, "size", "Size", True, "S")
    size_m = _attr(db, "size", "Size", True, "M")
    brass = _attr(db, "material", "Material", False, "Brass")

    products = {
        "jhumka": make_product(
            db, cats["earrings"], sku="JW-EAR-001", name="Temple Jhumka Earrings", tax=tax,
            short_description="Gold-plated temple jhumkas",
            variants=[
                {"sku": "JW-EAR-001-GLD", "name": "Gold", "mrp": "1299.00", "sale": "899.00", "cost": "300.00", "stock": 10, "attrs": [gold, brass]},
                {"sku": "JW-EAR-001-RED", "name": "Red", "mrp": "1299.00", "sale": "999.00", "cost": "320.00", "stock": 3, "attrs": [red, brass]},
            ]),
        "choker": make_product(
            db, cats["necklaces"], sku="JW-NCK-001", name="Kundan Choker Necklace", tax=tax, max_order_qty=3,
            variants=[{"sku": "JW-NCK-001", "name": "Gold", "mrp": "2499.00", "sale": "1999.00", "cost": "700.00", "stock": 5, "attrs": [gold, brass]}]),
        "ring": make_product(
            db, cats["rings"], sku="JW-RNG-001", name="Oxidised Silver Ring", tax=tax,
            variants=[{"sku": "JW-RNG-001", "name": "Silver", "mrp": "499.00", "sale": "499.00", "stock": 0, "attrs": [silver]}]),
        "kurti": make_product(
            db, cats["kurtis"], sku="AP-KRT-001", name="Indigo Cotton Kurti", product_type="apparel", tax=tax5,
            variants=[
                {"sku": "AP-KRT-001-S", "name": "Blue / S", "mrp": "999.00", "sale": "599.00", "stock": 20, "attrs": [blue, size_s]},
                {"sku": "AP-KRT-001-M", "name": "Blue / M", "mrp": "999.00", "sale": "599.00", "stock": 20, "attrs": [blue, size_m]},
            ]),
        "archived": make_product(
            db, cats["jewellery"], sku="JW-BRC-OLD", name="Retired Brass Bracelet", tax=tax, status="archived",
            variants=[{"sku": "JW-BRC-OLD", "name": "Gold", "mrp": "799.00", "sale": "599.00", "stock": 4, "attrs": [gold]}]),
    }
    variants = {v.sku: v for p in products.values() for v in p.variants}

    ship = ShippingMethod(code="standard", name="Standard Delivery", base_charge=Decimal("79.00"), min_days=3, max_days=6,
                          is_cod_allowed=True, is_active=True, display_order=1)
    db.add(ship)
    db.add_all([
        ServiceablePinCode(pin_code="110", city="Delhi", state="Delhi", region="metro", extra_days=0),
        ServiceablePinCode(pin_code="682551", city="Kavaratti", state="Lakshadweep", region="remote", is_serviceable=False,
                           is_cod_available=False),
    ])
    db.flush()
    return Catalog(tax=tax, cats=cats, products=products, variants=variants,
                   attrs={"gold": gold, "red": red, "blue": blue, "silver": silver}, shipping=ship)


@pytest.fixture
def catalog(db) -> Catalog:
    cat = build_catalog(db)
    db.commit()
    return cat


@pytest.fixture
def users(db, catalog) -> SimpleNamespace:
    ns = SimpleNamespace(
        admin=make_user(db, "admin@test.example.com", "admin", name="Store Admin"),
        staff=make_user(db, "staff@test.example.com", "staff", name="Ops Staff"),
        customer=make_user(db, "priya@test.example.com", "customer", name="Priya Sharma", phone="9810012345"),
        customer2=make_user(db, "ananya@test.example.com", "customer", name="Ananya Reddy"),
    )
    db.commit()
    return ns


@pytest.fixture
def admin_h(users):
    return headers_for(users.admin)


@pytest.fixture
def staff_h(users):
    return headers_for(users.staff)


@pytest.fixture
def cust_h(users):
    return headers_for(users.customer)


# ----------------------------------------------------------------------------- flow helpers
def add_to_cart(client: TestClient, headers: dict, variant_id: int, quantity: int = 1) -> dict:
    r = client.post("/api/v1/cart/items", json={"variant_id": variant_id, "quantity": quantity}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def guest_cart(client: TestClient) -> dict:
    """A fresh guest cart: the server issues the token, which is then sent as X-Cart-Token."""
    r = client.get("/api/v1/cart")
    assert r.status_code == 200, r.text
    return {"X-Cart-Token": r.json()["token"]}


GUEST_ADDRESS = {"full_name": "Guest Shopper", "phone": "9876543210", "line1": "1 Main Road", "city": "New Delhi",
                 "state": "Delhi", "pin_code": "110001"}


def checkout(client: TestClient, headers: dict, *, payment_method: str = "razorpay", address: dict | None = None,
             idempotency_key: str | None = None, expect: int = 201, **body) -> dict:
    h = dict(headers)
    if idempotency_key:
        h["Idempotency-Key"] = idempotency_key
    payload = {"shipping_address": address or ADDRESS, "payment_method": payment_method, **body}
    r = client.post("/api/v1/checkout", json=payload, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def place_order(client: TestClient, headers: dict, items: list[tuple[int, int]], payment_method: str = "razorpay", **kw) -> dict:
    for vid, qty in items:
        add_to_cart(client, headers, vid, qty)
    return checkout(client, headers, payment_method=payment_method, **kw)["order"]


def start_payment(client: TestClient, headers: dict, order: dict) -> dict:
    r = client.post("/api/v1/payments/razorpay/create-order",
                    json={"order_id": str(order["id"]), "order_key": order.get("order_key")}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def mock_pay(client: TestClient, rzp_order_id: str, outcome: str = "success") -> dict:
    r = client.post("/api/v1/payments/razorpay/mock-checkout", json={"razorpay_order_id": rzp_order_id, "outcome": outcome})
    assert r.status_code == 200, r.text
    return r.json()


def verify(client: TestClient, sim: dict):
    return client.post("/api/v1/payments/razorpay/verify", json={
        "razorpay_order_id": sim["razorpay_order_id"], "razorpay_payment_id": sim["razorpay_payment_id"],
        "razorpay_signature": sim["razorpay_signature"]})


def pay_order(client: TestClient, headers: dict, order: dict) -> dict:
    data = start_payment(client, headers, order)
    sim = mock_pay(client, data["razorpay_order_id"])
    r = verify(client, sim)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid"
    return r.json()["order"]


def inv(db, variant_id: int) -> Inventory:
    db.expire_all()
    return db.scalar(select(Inventory).where(Inventory.variant_id == variant_id))
