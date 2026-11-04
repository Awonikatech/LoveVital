"""Idempotent demo seed. Safe to re-run: every record is upserted by a natural key and sample
orders are keyed by idempotency keys, so nothing is duplicated.

    python -m scripts.seed            # seed everything
    python -m scripts.seed --no-orders

Development only — refuses to run when ENVIRONMENT=production.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.core.deps import ROLE_PERMISSIONS
from app.core.money import q
from app.core.security import hash_password
from app.integrations.razorpay_gateway import MockRazorpayGateway, get_gateway, set_gateway
from app.models import (
    Address,
    Banner,
    Cart,
    Category,
    CmsPage,
    Collection,
    Coupon,
    CouponRedemption,
    Inventory,
    InventoryMovement,
    InventoryReservation,
    NewsletterSubscriber,
    Order,
    OrderStatusHistory,
    Payment,
    PaymentEvent,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductImage,
    ProductReview,
    ProductVariant,
    Promotion,
    Refund,
    ReturnRequest,
    Role,
    ServiceablePinCode,
    Shipment,
    ShipmentEvent,
    ShippingMethod,
    TaxRate,
    User,
)
from app.services import cart_service, catalog_service, fulfilment_service, inventory_service, order_service, payment_service
from app.services.common import DEFAULT_SETTINGS, set_setting, slugify
from scripts import seed_catalog as C

R = random.Random(42)


def log(msg: str) -> None:
    print(f"  · {msg}")


# ------------------------------------------------------------------ users
CUSTOMERS = [
    ("Priya Sharma", settings.SEED_CUSTOMER_EMAIL, "9810012345", ("Flat 402, Lotus Residency", "Sector 50", "Noida", "Uttar Pradesh", "201301")),
    ("Ananya Reddy", "ananya.reddy@example.com", "9845012345", ("12, 4th Cross, Indiranagar", None, "Bengaluru", "Karnataka", "560038")),
    ("Meher Kapoor", "meher.kapoor@example.com", "9811122233", ("B-14, Greater Kailash II", None, "New Delhi", "Delhi", "110048")),
    ("Sneha Patil", "sneha.patil@example.com", "9822233344", ("Flat 7, Shanti Kunj, Kothrud", None, "Pune", "Maharashtra", "411038")),
    ("Farah Siddiqui", "farah.s@example.com", "9849033344", ("Plot 88, Banjara Hills Rd 12", None, "Hyderabad", "Telangana", "500034")),
    ("Kavya Iyer", "kavya.iyer@example.com", "9840044455", ("21, TTK Road, Alwarpet", None, "Chennai", "Tamil Nadu", "600018")),
    ("Riya Banerjee", "riya.b@example.com", "9830055566", ("44A, Lake Gardens", None, "Kolkata", "West Bengal", "700045")),
    ("Ishita Mehta", "ishita.mehta@example.com", "9825066677", ("9, Satellite Road", "Near Jodhpur Cross Roads", "Ahmedabad", "Gujarat", "380015")),
    ("Aditi Joshi", "aditi.joshi@example.com", "9819077788", ("1102, Sea Breeze, Bandra West", None, "Mumbai", "Maharashtra", "400050")),
    ("Nandini Rao", "nandini.rao@example.com", "9828088899", ("C-5, Malviya Nagar", None, "Jaipur", "Rajasthan", "302017")),
    ("Pooja Verma", "pooja.verma@example.com", "9839099900", ("27, Gomti Nagar Extension", None, "Lucknow", "Uttar Pradesh", "226010")),
    ("Tanvi Kulkarni", "tanvi.k@example.com", "9890011122", ("Row House 3, Baner", None, "Pune", "Maharashtra", "411045")),
    ("Zoya Khan", "zoya.khan@example.com", "9876543210", ("House 5, Gandhi Road", None, "Dehradun", "Uttarakhand", "248001")),
]


def role(db: Session, name: str) -> Role:
    r = db.scalar(select(Role).where(Role.name == name))
    if not r:
        r = Role(name=name, description={"admin": "Full access", "staff": "Store operations (no finance/cost data)",
                                         "customer": "Shopper"}[name], permissions=ROLE_PERMISSIONS[name])
        db.add(r)
        db.flush()
    else:
        r.permissions = ROLE_PERMISSIONS[name]
    return r


def upsert_user(db: Session, email: str, name: str, password: str, roles: list[Role], phone: str | None = None, verified=True) -> User:
    u = db.scalar(select(User).where(User.email == email.lower()))
    if not u:
        u = User(email=email.lower(), full_name=name, phone=phone, password_hash=hash_password(password),
                 email_verified_at=utcnow() if verified else None)
        db.add(u)
    for r in roles:
        if r not in u.roles:
            u.roles.append(r)
    db.flush()
    return u


def seed_users(db: Session) -> tuple[User, list[User]]:
    admin_r, staff_r, cust_r = role(db, "admin"), role(db, "staff"), role(db, "customer")
    admin = upsert_user(db, settings.SEED_ADMIN_EMAIL, "Store Admin", settings.SEED_ADMIN_PASSWORD, [admin_r])
    upsert_user(db, settings.SEED_STAFF_EMAIL, "Ops Staff", settings.SEED_STAFF_PASSWORD, [staff_r])
    customers = []
    for i, (name, email, phone, (l1, l2, city, state, pin)) in enumerate(CUSTOMERS):
        pw = settings.SEED_CUSTOMER_PASSWORD
        u = upsert_user(db, email, name, pw, [cust_r], phone, verified=i % 4 != 3)
        if not u.addresses:
            db.add(Address(user_id=u.id, label="Home", full_name=name, phone=phone, line1=l1, line2=l2, city=city, state=state,
                           pin_code=pin, is_default_shipping=True, is_default_billing=True))
            if i == 0:
                db.add(Address(user_id=u.id, label="Office", full_name=name, phone=phone, line1="Tower B, 9th Floor, Candor TechSpace",
                               line2="Sector 62", city="Noida", state="Uttar Pradesh", pin_code="201309"))
        customers.append(u)
    db.flush()
    # spread sign-up dates over the last ~5 months for acquisition reports
    for i, u in enumerate(customers):
        if u.created_at > utcnow() - timedelta(minutes=10):
            u.created_at = utcnow() - timedelta(days=150 - i * 11)
    log(f"users: admin, staff, {len(customers)} customers")
    return admin, customers


# ------------------------------------------------------------------ catalog
def seed_catalog(db: Session, admin: User) -> None:
    taxes = {
        "jw": ("GST 3% — Imitation Jewellery", "7117", Decimal("3.00")),
        "ap5": ("GST 5% — Apparel up to ₹2,500", "6204", Decimal("5.00")),
        "ap18": ("GST 18% — Apparel above ₹2,500", "6204", Decimal("18.00")),
    }
    tax_rows = {}
    for key, (name, hsn, rate) in taxes.items():
        t = db.scalar(select(TaxRate).where(TaxRate.name == name)) or TaxRate(name=name)
        t.hsn_code, t.rate, t.is_active = hsn, rate, True
        db.add(t)
        db.flush()
        tax_rows[key] = t

    attr_values: dict[tuple[str, str], ProductAttributeValue] = {}
    for code, name, display, axis, order, values in C.ATTRIBUTES:
        a = db.scalar(select(ProductAttribute).where(ProductAttribute.code == code))
        if not a:
            a = ProductAttribute(code=code, name=name)
            db.add(a)
        a.name, a.display_type, a.is_variant_axis, a.display_order, a.is_filterable = name, display, axis, order, code not in ("sleeve",)
        db.flush()
        for i, v in enumerate(values):
            slug = slugify(v)
            av = db.scalar(select(ProductAttributeValue).where(ProductAttributeValue.attribute_id == a.id, ProductAttributeValue.slug == slug))
            if not av:
                av = ProductAttributeValue(attribute_id=a.id, value=v, slug=slug)
                db.add(av)
            av.display_order = i
            av.swatch_hex = C.SWATCH.get(v) if code == "color" else None
            db.flush()
            attr_values[(code, v)] = av

    cats: dict[str, Category] = {}
    for slug, name, parent, desc, order in C.CATEGORIES:
        c = db.scalar(select(Category).where(Category.slug == slug)) or Category(slug=slug)
        c.name, c.description, c.display_order, c.is_active = name, desc, order, True
        c.parent_id = cats[parent].id if parent else None
        c.image_url = f"/static/tiles/{slug}.svg"
        c.seo_title = f"{name} — Shop Online | LoveVital"
        c.seo_description = desc
        db.add(c)
        db.flush()
        cats[slug] = c

    cols: dict[str, Collection] = {}
    for slug, name, desc, featured, order in C.COLLECTIONS:
        col = db.scalar(select(Collection).where(Collection.slug == slug)) or Collection(slug=slug)
        col.name, col.description, col.is_featured, col.display_order, col.is_active = name, desc, featured, order, True
        col.image_url = f"/static/tiles/{slug}.svg"
        db.add(col)
        db.flush()
        cols[slug] = col

    created = 0
    for idx, spec in enumerate(C.PRODUCTS):
        p = db.scalar(select(Product).where(Product.sku == spec["sku"]))
        is_new = p is None
        if is_new:
            p = Product(sku=spec["sku"], slug=spec["slug"], name=spec["name"], product_type=spec["kind"], category_id=cats[spec["cat"]].id)
            db.add(p)
            created += 1
        flags = spec["flags"].split(",") if spec["flags"] else []
        jew = spec["kind"] == "jewellery"
        p.name, p.slug, p.product_type, p.category_id = spec["name"], spec["slug"], spec["kind"], cats[spec["cat"]].id
        p.brand = "LoveVital" if idx % 5 else ("LoveVital Heritage" if jew else "LoveVital Studio")
        p.short_description = spec["desc"].split(". ")[0].rstrip(".") + "."
        p.description = spec["desc"] + ("\n\nEach piece is hand-finished by our artisans, so minor variations are part of its charm."
                                        if jew else "\n\nModel is 5'6\" and wears size S.")
        p.tags = spec["tags"] or None
        p.status = "active"
        p.is_featured, p.is_bestseller, p.is_new_arrival = "featured" in flags, "bestseller" in flags, "new" in flags
        p.processing_days = spec["processing"]
        p.is_returnable = spec["returnable"]
        p.return_window_days = 7
        p.max_order_qty = 5 if spec["sale"] > 3000 else 10
        p.is_cod_available = spec["sale"] <= 9000
        if jew:
            p.tax_rate_id = tax_rows["jw"].id
            p.care_instructions = C.JW_CARE
            p.specifications = {"Warranty": "6-month plating warranty", "Country of Origin": "India",
                                **({"Approx. Weight": f"{spec['weight']} g"} if spec.get("weight") else {}),
                                "Closure": {"earrings": "Push-back", "oxidised-earrings": "Hook", "rings": "Open band" if spec.get("sizes") == ["Adjustable"] else "Closed band"}.get(spec["cat"], "Lobster clasp / adjustable dori")}
            chart = {"ring": C.SIZE_CHART_RING, "bangle": C.SIZE_CHART_BANGLE}.get(spec.get("chart") or "")
        else:
            p.tax_rate_id = tax_rows["ap18" if spec["sale"] > 2500 else "ap5"].id
            p.care_instructions = C.AP_CARE.get(spec["attrs"]["fabric"], "Dry clean recommended.")
            p.specifications = {"Pattern": "Embroidered" if spec["attrs"]["occasion"] in ("Festive", "Wedding") else "Printed",
                                "Neck": "Round" if spec["art"] in ("kurti", "kurti-short", "top") else "V-neck", "Country of Origin": "India",
                                "Package Contains": "1 saree with unstitched blouse piece" if spec["cat"] == "sarees" else "1 garment"}
            chart = {"top": C.SIZE_CHART_TOP, "bottom": C.SIZE_CHART_BOTTOM}.get(spec.get("chart") or "")
        p.size_chart = chart
        p.seo_title = f"{spec['name']} | LoveVital"
        p.seo_description = p.short_description[:160]
        p.published_at = p.published_at or (utcnow() - timedelta(days=(3 if "new" in flags else 40 + idx)))
        db.flush()

        # shared (non-axis) attribute values
        shared = []
        if jew:
            for code in ("stone", "style", "material", "occasion"):
                shared.append(attr_values[(code, spec["attrs"][code])])
        else:
            for code in ("fabric", "fit", "sleeve", "style", "occasion"):
                shared.append(attr_values[(code, spec["attrs"][code])])

        sizes = spec["sizes"] or [None]
        existing = {v.sku: v for v in p.variants}
        order_i = 0
        mrp, sale = Decimal(spec["mrp"]), Decimal(spec["sale"])
        for ci, color in enumerate(spec["colors"]):
            for size in sizes:
                order_i += 1
                if len(spec["colors"]) == 1 and size is None:
                    vsku = spec["sku"]
                else:
                    vsku = spec["sku"] + "-" + slugify(color)[:3].upper() + (f"-{slugify(size).upper().replace('-', '')}" if size else "")
                v = existing.get(vsku)
                if not v:
                    v = ProductVariant(product=p, sku=vsku)
                    p.variants.append(v)
                v.name = " / ".join(x for x in (color, size) if x)
                bump = Decimal(100) if (size in ("XL", "XXL") and spec["mrp"] > 1500) else Decimal(0)
                v.mrp, v.sale_price = q(mrp + bump), q(sale + bump)
                v.cost_price = q((sale + bump) * Decimal(str(spec["cost_pct"])))
                v.weight_grams = Decimal(spec["weight"]) if spec.get("weight") else None
                v.is_active, v.is_default, v.display_order = True, order_i == 1, order_i
                vals = list(shared)
                vals.append(attr_values[("color", color)])
                if size:
                    vals.append(attr_values[("size", size)])
                if jew:
                    vals.append(attr_values[("plating", spec["plating"] or C.PLATING_FOR.get(color, "Gold-plated"))])
                v.attribute_values = vals
                db.flush()
                if v.inventory is None:
                    base = spec["stock"] if not size else max(2, spec["stock"] // max(1, len(sizes) - 1))
                    stock = base if (idx + order_i) % 11 else R.choice([0, 2, 3])  # a few low/out-of-stock variants
                    v.inventory = Inventory(variant_id=v.id, quantity_on_hand=0, quantity_reserved=0, low_stock_threshold=5 if jew else 3)
                    db.flush()
                    if stock:
                        inventory_service.adjust(db, v.id, stock, "initial", "Opening stock", admin)
        # images: per colour look, 3 views for the first look
        if not p.images:
            color_variant = {}
            for v in p.variants:
                c0 = v.name.split(" / ")[0]
                color_variant.setdefault(c0, []).append(v)
            for li, look in enumerate(spec["looks"]):
                views = 3 if li == 0 else 1
                for view in range(views):
                    db.add(ProductImage(product_id=p.id, url=f"/static/products/{spec['slug']}-{li}-{view}.svg",
                                        alt_text=f"{spec['name']} — {look['color']}" + ("" if view == 0 else [" detail", " detail", " flat lay"][view]),
                                        display_order=li * 10 + view, is_primary=(li == 0 and view == 0),
                                        variant_id=color_variant[look["color"]][0].id if (view == 0 and len(spec["looks"]) > 1) else None))
        p.collections = [cols[c] for c in spec["collections"]]
        db.flush()
        db.refresh(p)
        catalog_service.refresh_product_aggregates(db, p)
    log(f"catalog: {len(C.CATEGORIES)} categories, {len(C.COLLECTIONS)} collections, {len(C.PRODUCTS)} products ({created} new)")


# ------------------------------------------------------------------ commerce config
def seed_commerce(db: Session) -> None:
    methods = [
        ("standard", "Standard Delivery", "Tracked delivery in 3–6 business days", "BlueRiver Express", "79.00", None, 3, 6, True, 1),
        ("express", "Express Delivery", "Priority dispatch, 1–3 business days in metros", "Swift Air Couriers", "149.00", "2999.00", 1, 3, True, 2),
    ]
    for code, name, desc, carrier, charge, thr, mn, mx, cod, order in methods:
        m = db.scalar(select(ShippingMethod).where(ShippingMethod.code == code)) or ShippingMethod(code=code)
        m.name, m.description, m.carrier, m.base_charge = name, desc, carrier, Decimal(charge)
        m.free_shipping_threshold = Decimal(thr) if thr else None
        m.min_days, m.max_days, m.is_cod_allowed, m.display_order, m.is_active = mn, mx, cod, order, True
        db.add(m)
    pins = [
        ("110", "Delhi", "Delhi", "metro", 0, True, True), ("201", "Noida / Ghaziabad", "Uttar Pradesh", "metro", 0, True, True),
        ("122", "Gurugram", "Haryana", "metro", 0, True, True), ("400", "Mumbai", "Maharashtra", "metro", 0, True, True),
        ("560", "Bengaluru", "Karnataka", "metro", 0, True, True), ("600", "Chennai", "Tamil Nadu", "metro", 0, True, True),
        ("700", "Kolkata", "West Bengal", "metro", 0, True, True), ("500", "Hyderabad", "Telangana", "metro", 0, True, True),
        ("411", "Pune", "Maharashtra", "metro", 0, True, True), ("380", "Ahmedabad", "Gujarat", "regional", 1, True, True),
        ("302", "Jaipur", "Rajasthan", "regional", 1, True, True), ("226", "Lucknow", "Uttar Pradesh", "regional", 1, True, True),
        ("248", "Dehradun", "Uttarakhand", "regional", 1, True, True), ("781", "Guwahati", "Assam", "remote", 3, True, True),
        ("737", "Gangtok", "Sikkim", "remote", 3, True, False), ("744", "Port Blair", "Andaman and Nicobar Islands", "remote", 5, True, False),
        ("194", "Leh", "Ladakh", "remote", 5, True, False), ("682551", "Kavaratti", "Lakshadweep", "remote", 0, False, False),
        ("110001", "Connaught Place", "Delhi", "metro", 0, True, True),
    ]
    for pin, city, state, region, extra, svc, cod in pins:
        r = db.scalar(select(ServiceablePinCode).where(ServiceablePinCode.pin_code == pin)) or ServiceablePinCode(pin_code=pin)
        r.city, r.state, r.region, r.extra_days, r.is_serviceable, r.is_cod_available = city, state, region, extra, svc, cod
        db.add(r)
    now = utcnow()
    cat = {c.slug: c.id for c in db.scalars(select(Category)).all()}
    prod = {p.sku: p.id for p in db.scalars(select(Product)).all()}
    coupons = [
        dict(code="WELCOME15", description="15% off your first order (max ₹300)", discount_type="percent", value=15, max_discount=300,
             first_order_only=True, usage_limit_per_user=1),
        dict(code="FESTIVE10", description="Festive Edit: 10% off on ₹1,499+ (max ₹500)", discount_type="percent", value=10, min_cart_value=1499,
             max_discount=500, usage_limit_per_user=3, ends_at=now + timedelta(days=45)),
        dict(code="FLAT200", description="₹200 off on orders above ₹1,999", discount_type="fixed", value=200, min_cart_value=1999, usage_limit_per_user=2,
             usage_limit_total=500),
        dict(code="FREESHIP", description="Free shipping, no minimum", discount_type="free_shipping", value=0, usage_limit_per_user=5),
        dict(code="JEWEL20", description="20% off jewellery (can't be combined with offers)", discount_type="percent", value=20, max_discount=1000,
             applies_to="categories", category_ids=[cat["jewellery"], cat["silver-oxidised"], cat["bridal-jewellery"]],
             combinable_with_promotions=False, min_cart_value=999),
        dict(code="SAREE300", description="₹300 off any saree", discount_type="fixed", value=300, applies_to="categories", category_ids=[cat["sarees"]]),
        dict(code="VIPPRIYA", description="Private ₹500 voucher", discount_type="fixed", value=500, min_cart_value=2500,
             customer_emails=[settings.SEED_CUSTOMER_EMAIL]),
        dict(code="SUMMER25", description="Expired summer sale", discount_type="percent", value=25, starts_at=now - timedelta(days=150),
             ends_at=now - timedelta(days=90)),
        dict(code="EARRING100", description="₹100 off the signature jhumkas", discount_type="fixed", value=100, applies_to="products",
             product_ids=[prod["JW-EAR-001"]]),
    ]
    for cfg in coupons:
        c = db.scalar(select(Coupon).where(Coupon.code == cfg["code"])) or Coupon(code=cfg["code"], discount_type=cfg["discount_type"])
        base = dict(min_cart_value=0, max_discount=None, starts_at=None, ends_at=None, usage_limit_total=None, usage_limit_per_user=None,
                    first_order_only=False, applies_to="all", category_ids=None, product_ids=None, customer_emails=None,
                    combinable_with_promotions=True, is_active=True)
        for k, v in {**base, **cfg}.items():
            if k in ("value", "min_cart_value", "max_discount") and v is not None:
                v = Decimal(str(v))
            setattr(c, k, v)
        db.add(c)
    promos = [
        dict(name="Buy 1 Get 1 on Everyday Studs", description="Buy any 2 studs, the lower-priced pair is free", badge_text="Buy 1 Get 1",
             promo_type="bogo", value=0, config={"buy_qty": 1, "get_qty": 1, "get_discount_pct": 100}, applies_to="products",
             product_ids=[prod["JW-EAR-004"], prod["JW-EAR-005"]], priority=10, is_stackable=False),
        dict(name="Bangle Stack Offer", description="Buy 3 or more bangle sets & kadas, get 15% off", badge_text="3+ for 15% off",
             promo_type="quantity_discount", value=15, config={"min_qty": 3}, applies_to="categories", category_ids=[cat["bangles"]], priority=20),
        dict(name="Ethnic Weekend", description="Extra 5% off ethnic wear", badge_text="Extra 5% off", promo_type="percent_off", value=5,
             config={"max_discount": 400}, applies_to="categories", category_ids=[cat["ethnic-wear"]], priority=50, ends_at=now + timedelta(days=21)),
        dict(name="Free Shipping on Festive & Bridal", description="Free delivery on festive & bridal pieces", badge_text="Free shipping",
             promo_type="free_shipping", value=0, config={}, applies_to="categories", category_ids=[cat["festive-bridal"]], priority=90),
    ]
    for cfg in promos:
        p = db.scalar(select(Promotion).where(Promotion.name == cfg["name"])) or Promotion(name=cfg["name"], promo_type=cfg["promo_type"])
        base = dict(applies_to="all", category_ids=None, product_ids=None, is_stackable=True, is_active=True, starts_at=None, ends_at=None)
        for k, v in {**base, **cfg}.items():
            setattr(p, k, Decimal(str(v)) if k == "value" else v)
        db.add(p)
    banners = [
        ("The Festive Edit", "Kundan, zari & jewel tones — handcrafted for every celebration.", "New season for Diwali 2026",
         "/static/banners/hero-festive.svg", "Shop the Edit", "/collections/festive-edit", "hero", 1),
        ("Heritage Jhumkas from ₹399", "Temple, meenakari and oxidised jhumkas that sing with every step.", "Our bestsellers",
         "/static/banners/hero-jhumka.svg", "Shop Earrings", "/category/earrings", "hero", 2),
        ("Silk & Zari Sarees", "Banarasi-inspired weaves with an extra 5% off this weekend.", "Ethnic weekend",
         "/static/banners/hero-saree.svg", "Explore Sarees", "/category/sarees", "hero", 3),
        ("The Wedding Season Shop", "Bridal sets, lehengas & heirloom-look jewellery. Free shipping.", "Bridal",
         "/static/banners/promo-bridal.svg", "Shop Bridal", "/collections/wedding-season", "promo", 1),
        ("Everyday Minimal", "Light, wearable pieces from ₹349 — desk to dinner.", "Under ₹999",
         "/static/banners/promo-minimal.svg", "Shop Minimal", "/collections/everyday-minimal", "promo", 2),
    ]
    for title, sub, eyebrow, img, cta, link, placement, order in banners:
        b = db.scalar(select(Banner).where(Banner.title == title, Banner.placement == placement)) or Banner(title=title, placement=placement)
        b.subtitle, b.eyebrow, b.image_url, b.cta_text, b.cta_link, b.display_order, b.is_active = sub, eyebrow, img, cta, link, order, True
        db.add(b)
    for slug, (title, body) in C.PAGES.items():
        pg = db.scalar(select(CmsPage).where(CmsPage.slug == slug)) or CmsPage(slug=slug, title=title, body=body)
        if not pg.id:
            db.add(pg)
        pg.title, pg.seo_title, pg.seo_description = title, f"{title} | LoveVital", body.split("\n")[2][:160] if "\n" in body else title
        if not pg.body:
            pg.body = body
        else:
            for old, new in (
                ("Swarnika", "LoveVital"),
                ("care@swarnika.example.com", "janviawadhesh@gmail.com"),
                ("care@lovevital.example.com", "janviawadhesh@gmail.com"),
                ("+91 98100 00000", "+91-8744092014"),
                ("Plot 21, Sector 63, Noida, Uttar Pradesh 201301", "B1601, Samridhi Grand Avenue, Greater Noida (W), Uttar Pradesh 201305"),
            ):
                pg.body = pg.body.replace(old, new)
    for key, (value, desc, public) in DEFAULT_SETTINGS.items():
        from app.models import StoreSetting

        setting = db.scalar(select(StoreSetting).where(StoreSetting.key == key))
        if not setting:
            db.add(StoreSetting(key=key, value=value, description=desc, is_public=public))
        elif key == "store_name" and setting.value == "Swarnika":
            setting.value = "LoveVital"
        elif key == "support_email" and setting.value == "care@swarnika.example.com":
            setting.value = "janviawadhesh@gmail.com"
        elif key == "support_email" and setting.value == "care@lovevital.example.com":
            setting.value = "janviawadhesh@gmail.com"
        elif key == "support_phone" and setting.value == "+91 98100 00000":
            setting.value = "+91-8744092014"
        elif key == "store_address" and setting.value == "Plot 21, Sector 63, Noida, Uttar Pradesh 201301":
            setting.value = "B1601, Samridhi Grand Avenue, Greater Noida (W), Uttar Pradesh 201305"
    for e in ["hello.ritu@example.com", "neha.g@example.com", "simran.k@example.com", "avni.m@example.com", settings.SEED_CUSTOMER_EMAIL]:
        if not db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email == e)):
            db.add(NewsletterSubscriber(email=e, status="subscribed", source="footer"))
    db.flush()
    log("commerce: shipping methods, PIN rules, coupons, promotions, banners, pages, settings")


# ------------------------------------------------------------------ orders
def _variant(db: Session, sku_prefix: str, pick: int = 0) -> ProductVariant:
    vs = db.scalars(select(ProductVariant).join(Product).where(Product.sku == sku_prefix, ProductVariant.is_active.is_(True)).order_by(ProductVariant.display_order)).all()
    in_stock = [v for v in vs if v.inventory and v.inventory.available > 2] or vs
    return in_stock[pick % len(in_stock)]


def _backdate(db: Session, order: Order, when) -> None:
    delta = utcnow() - when
    order.placed_at -= delta
    order.created_at -= delta
    for attr in ("paid_at", "cancelled_at", "delivered_at"):
        if getattr(order, attr):
            setattr(order, attr, getattr(order, attr) - delta)
    if order.estimated_delivery_date:
        order.estimated_delivery_date -= timedelta(days=delta.days)
        order.estimated_dispatch_date -= timedelta(days=delta.days)
    for h in db.scalars(select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id).order_by(OrderStatusHistory.id)).all():
        h.created_at -= delta
    for model in (Payment, Refund, Shipment, ReturnRequest, InventoryReservation):
        for row in db.scalars(select(model).where(model.order_id == order.id)).all():
            row.created_at -= delta
            for attr in ("captured_at", "processed_at", "shipped_at", "delivered_at", "resolved_at", "expires_at", "released_at"):
                if getattr(row, attr, None):
                    setattr(row, attr, getattr(row, attr) - delta)
            if isinstance(row, Shipment):
                for e in row.events:
                    e.occurred_at -= delta
    for row in db.scalars(select(CouponRedemption).where(CouponRedemption.order_id == order.id)).all():
        row.created_at -= delta
    for m in db.scalars(select(InventoryMovement).where(InventoryMovement.reference_id == order.order_number)).all():
        m.created_at -= delta
    for ev in db.scalars(select(PaymentEvent).join(Payment, Payment.id == PaymentEvent.payment_id).where(Payment.order_id == order.id)).all():
        ev.received_at -= delta
        if ev.processed_at:
            ev.processed_at -= delta


def _place(db: Session, key: str, user: User, items: list[tuple[str, int, int]], method: str, coupon: str | None = None,
           express: bool = False) -> Order | None:
    existing = db.scalar(select(Order).where(Order.idempotency_key == f"{user.id}:{key}"))
    if existing:
        return None
    cart = Cart(token=f"seed-{key}-{R.randint(0, 10**9)}", user_id=user.id, status="active")
    db.add(cart)
    db.flush()
    for sku, qty, pick in items:
        v = _variant(db, sku, pick)
        if not v.inventory or v.inventory.available < qty:
            inventory_service.adjust(db, v.id, qty + 10, "restock", "Seed restock", None)
            db.refresh(v)
        cart_service.add_item(db, cart, v.id, qty)
    addrs = db.scalars(select(Address).where(Address.user_id == user.id).order_by(Address.is_default_shipping.desc(), Address.id)).all()
    addr = addrs[0]
    m = db.scalar(select(ShippingMethod).where(ShippingMethod.code == ("express" if express else "standard")))
    order, _ = order_service.create_order(db, cart=cart, user=user, email=user.email, phone=user.phone, shipping_address=addr,
                                          billing_address=None, shipping_method_id=m.id, payment_method=method, coupon_code=coupon,
                                          customer_note=None, idempotency_key=key)
    return order


def _pay(db: Session, order: Order, succeed: bool = True, method: str = "upi") -> None:
    data = payment_service.create_payment_order(db, order)
    gw: MockRazorpayGateway = get_gateway()  # type: ignore[assignment]
    sim = gw.simulate_payment(data["razorpay_order_id"], data["amount"], method, succeed)
    if succeed:
        payment_service.verify_payment(db, data["razorpay_order_id"], sim["payment"]["id"], sim["signature"])
    else:
        payment_service.report_failure(db, data["razorpay_order_id"], sim["payment"]["id"], "BAD_REQUEST_ERROR", "Payment declined by bank")


def _advance(db: Session, order: Order, admin: User, upto: str) -> None:
    steps = ["processing", "packed", "shipped", "out_for_delivery", "delivered"]
    for st in steps:
        if st == "processing":
            order_service.transition(db, order, "processing", actor=admin, note="Picked for packing")
        elif st == "packed":
            fulfilment_service.create_shipment(db, order, admin, weight_grams=350)
        elif st == "shipped":
            fulfilment_service.update_shipment_status(db, order.shipments[-1], "shipped", admin)
            fulfilment_service.update_shipment_status(db, order.shipments[-1], "in_transit", admin, description="Arrived at sorting hub")
        else:
            fulfilment_service.update_shipment_status(db, order.shipments[-1], st, admin)
        if st == upto:
            break


SCENARIOS = [
    # key, customer idx, items [(sku, qty, variant pick)], method, coupon, end state, days ago, express, pay_method
    ("seed-01", 0, [("JW-EAR-001", 1, 0), ("AP-KRT-001", 1, 1)], "razorpay", "WELCOME15", "delivered", 52, False, "upi"),
    ("seed-02", 1, [("JW-NCK-001", 1, 0)], "razorpay", None, "delivered", 47, True, "card"),
    ("seed-03", 2, [("AP-SAR-001", 1, 0), ("JW-BNG-001", 1, 1)], "razorpay", "FESTIVE10", "delivered", 41, False, "netbanking"),
    ("seed-04", 3, [("JW-OXE-001", 2, 0), ("AP-TRS-002", 1, 0)], "cod", None, "delivered", 36, False, "cod"),
    ("seed-05", 4, [("JW-RNG-001", 1, 0), ("JW-PND-001", 1, 0)], "razorpay", None, "delivered", 30, False, "wallet"),
    ("seed-06", 5, [("AP-DRS-001", 1, 2)], "razorpay", "FLAT200", "delivered", 26, False, "upi"),
    ("seed-07", 6, [("JW-EAR-004", 2, 0)], "razorpay", None, "shipped", 4, False, "upi"),
    ("seed-08", 7, [("AP-TOP-001", 1, 1), ("AP-TRS-001", 1, 1)], "razorpay", None, "shipped", 3, True, "card"),
    ("seed-09", 8, [("JW-NCK-002", 1, 0)], "razorpay", None, "out_for_delivery", 3, True, "upi"),
    ("seed-10", 9, [("AP-KRT-004", 1, 0)], "cod", None, "packed", 2, False, "cod"),
    ("seed-11", 10, [("JW-BNG-003", 1, 0), ("JW-BNG-004", 2, 0)], "razorpay", None, "packed", 2, False, "upi"),
    ("seed-12", 11, [("AP-CRD-001", 1, 0)], "razorpay", None, "processing", 1, False, "netbanking"),
    ("seed-13", 0, [("JW-TKA-001", 1, 0), ("JW-EAR-003", 1, 0)], "razorpay", "FREESHIP", "processing", 1, False, "upi"),
    ("seed-14", 1, [("AP-LHG-002", 1, 1)], "razorpay", None, "payment_confirmed", 0, False, "card"),
    ("seed-15", 2, [("JW-BRC-001", 1, 0)], "razorpay", None, "payment_confirmed", 0, False, "upi"),
    ("seed-16", 3, [("AP-KRT-003", 2, 0)], "cod", None, "order_placed", 0, False, "cod"),
    ("seed-17", 4, [("JW-SLV-001", 1, 0)], "razorpay", None, "payment_pending_failed", 0, False, "upi"),
    ("seed-18", 5, [("JW-NCK-003", 1, 0)], "razorpay", None, "cancelled_refunded", 18, False, "upi"),
    ("seed-19", 6, [("AP-SAR-002", 1, 0)], "cod", None, "cancelled", 15, False, "cod"),
    ("seed-20", 7, [("JW-EAR-002", 1, 0), ("JW-EAR-006", 1, 0)], "razorpay", None, "cancellation_requested", 2, False, "upi"),
    ("seed-21", 8, [("AP-TOP-002", 1, 0)], "razorpay", None, "return_requested", 12, False, "card"),
    ("seed-22", 9, [("AP-KRT-002", 1, 0), ("JW-BRC-002", 1, 0)], "razorpay", None, "returned_refunded", 22, False, "upi"),
    ("seed-23", 10, [("JW-ANK-001", 1, 0)], "cod", None, "delivery_failed", 6, False, "cod"),
    ("seed-24", 11, [("AP-FST-001", 1, 0)], "razorpay", None, "refund_pending", 9, False, "upi"),
    ("seed-25", 12, [("JW-BRD-002", 1, 0)], "razorpay", None, "delivered", 20, True, "card"),
]
FILLER_SKUS = ["JW-EAR-001", "JW-EAR-003", "JW-EAR-005", "JW-OXE-002", "JW-NCK-001", "JW-NCK-004", "JW-BNG-002", "JW-BRC-001",
               "JW-RNG-002", "JW-PND-002", "AP-KRT-001", "AP-KRT-003", "AP-SAR-003", "AP-TOP-003", "AP-TRS-002", "AP-DRS-002",
               "JW-SLV-002", "JW-OXE-003", "AP-CRD-001", "JW-RNG-003"]


def seed_orders(db: Session, admin: User, customers: list[User]) -> None:
    prev_gw = get_gateway() if settings.RAZORPAY_MODE == "mock" else None
    set_gateway(MockRazorpayGateway("rzp_seed", settings.RAZORPAY_KEY_SECRET, settings.RAZORPAY_WEBHOOK_SECRET))
    import app.services.notification_service as ns

    ns.SYNC_DISPATCH = False
    made = 0
    try:
        scenarios = list(SCENARIOS)
        for i in range(40):  # filler history for charts & reports
            u = customers[i % len(customers)]
            items = [(R.choice(FILLER_SKUS), 1, R.randint(0, 3))]
            if R.random() < .35:
                items.append((R.choice(FILLER_SKUS), 1, R.randint(0, 3)))
            items = list({s: (s, qn, pk) for s, qn, pk in items}.values())
            scenarios.append((f"seed-h{i:02d}", i % len(customers), items, "cod" if R.random() < .22 else "razorpay", None, "delivered",
                              R.randint(8, 88), R.random() < .2, R.choice(["upi", "upi", "upi", "card", "card", "netbanking", "wallet"])))
        for key, ci, items, method, coupon, end, days, express, pay_method in scenarios:
            user = customers[ci]
            order = _place(db, key, user, items, method, coupon, express)
            if order is None:
                continue
            made += 1
            if method == "razorpay":
                if end == "payment_pending_failed":
                    _pay(db, order, succeed=False)
                else:
                    _pay(db, order, True, pay_method)
            if end in ("delivered", "shipped", "out_for_delivery", "packed", "processing", "delivery_failed", "return_requested", "returned_refunded"):
                target = {"return_requested": "delivered", "returned_refunded": "delivered", "delivery_failed": "out_for_delivery"}.get(end, end)
                _advance(db, order, admin, target)
            if end == "delivery_failed":
                fulfilment_service.update_shipment_status(db, order.shipments[-1], "delivery_failed", admin, description="Customer unavailable; will re-attempt")
            if end == "cancelled_refunded":
                order_service.cancel(db, order, actor=user, reason="Ordered the wrong colour", actor_type="customer")
            if end == "cancelled":
                order_service.cancel(db, order, actor=user, reason="Found a better option", actor_type="customer")
            if end == "cancellation_requested":
                _advance(db, order, admin, "packed")
                order_service.cancel(db, order, actor=user, reason="Need it delivered to a different city", actor_type="customer")
            if end in ("return_requested", "returned_refunded"):
                it = order.items[0]
                rr = order_service.request_return(db, order, user, [{"order_item_id": it.id, "quantity": 1}],
                                                  "size_issue" if end == "return_requested" else "quality_issue",
                                                  "Fits a bit tight around the shoulders." if end == "return_requested" else "Zari thread came loose.", "return")
                if end == "returned_refunded":
                    order_service.resolve_return(db, rr, "approve", admin, "Approved — pickup scheduled")
                    order_service.resolve_return(db, rr, "receive", admin, "Received in good condition")
            if end == "refund_pending":
                gw = get_gateway()
                orig = gw.refund
                gw.refund = lambda pid, amt, notes, key: {"id": f"rfnd_pend_{order.id}", "status": "pending", "amount": amt}  # type: ignore
                try:
                    _advance(db, order, admin, "processing")
                    order_service.cancel(db, order, actor=admin, reason="Item damaged during quality check", actor_type="admin")
                finally:
                    gw.refund = orig  # type: ignore
            db.flush()
            _backdate(db, order, utcnow() - timedelta(days=days, hours=R.randint(0, 20), minutes=R.randint(0, 59)))
            db.commit()
    finally:
        set_gateway(prev_gw)
    log(f"orders: {made} new sample orders across all statuses")


REVIEW_TEXT = {
    5: [("Absolutely stunning", "Looks far more expensive than it is. Got so many compliments at the wedding!"),
        ("Exactly as pictured", "Beautiful finish, sturdy and lightweight. Packaging was lovely too."),
        ("Perfect festive pick", "Wore it for Diwali puja — the colour is rich and the fit is perfect."),
        ("Love it!", "Second purchase from LoveVital and they never disappoint.")],
    4: [("Very pretty", "Lovely piece, slightly smaller than I expected but still gorgeous."),
        ("Good quality", "Nice craftsmanship. Delivery took a day longer than estimated."),
        ("Worth the price", "Elegant and comfortable. Would buy again in another colour.")],
    3: [("Decent", "Looks nice but the finish could be better at the back."),
        ("Okay for the price", "The colour is a little different from the photos.")],
}


def seed_reviews(db: Session, customers: list[User]) -> None:
    products = db.scalars(select(Product).where(Product.status == "active")).all()
    n = 0
    for p in products:
        k = 2 + (p.id % 4)
        for j in range(k):
            u = customers[(p.id * 3 + j * 5) % len(customers)]
            if db.scalar(select(ProductReview.id).where(ProductReview.product_id == p.id, ProductReview.user_id == u.id)):
                continue
            rating = R.choices([5, 4, 3], weights=[6, 3, 1])[0]
            title, body = R.choice(REVIEW_TEXT[rating])
            bought = db.scalar(select(Order.id).join(Order.items).where(Order.user_id == u.id, Order.status == "delivered",
                                                                       Order.items.any(product_id=p.id)).limit(1))
            r = ProductReview(product_id=p.id, user_id=u.id, order_id=bought, rating=rating, title=title, body=body,
                              is_verified_purchase=bool(bought) or j % 2 == 0, status="published")
            r.created_at = utcnow() - timedelta(days=R.randint(1, 80))
            db.add(r)
            n += 1
        db.flush()
        db.refresh(p)
        catalog_service.refresh_product_aggregates(db, p)
    log(f"reviews: {n} new")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-orders", action="store_true")
    args = ap.parse_args(argv)
    if settings.is_production:
        print("Refusing to seed demo data in production.", file=sys.stderr)
        sys.exit(1)
    print(f"Seeding {settings.DATABASE_URL.split('@')[-1]} ...")
    db = SessionLocal()
    try:
        admin, customers = seed_users(db)
        db.commit()
        seed_catalog(db, admin)
        db.commit()
        seed_commerce(db)
        db.commit()
        if not args.no_orders:
            seed_orders(db, admin, customers)
        seed_reviews(db, customers)
        db.commit()
        print("Done. Demo logins:")
        print(f"  admin    {settings.SEED_ADMIN_EMAIL} / {settings.SEED_ADMIN_PASSWORD}")
        print(f"  staff    {settings.SEED_STAFF_EMAIL} / {settings.SEED_STAFF_PASSWORD}")
        print(f"  customer {settings.SEED_CUSTOMER_EMAIL} / {settings.SEED_CUSTOMER_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
