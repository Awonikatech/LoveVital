"""Carts (guest via X-Cart-Token, persistent for logged-in users) and server-side pricing of a cart."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.errors import NotFound, ValidationFailed
from app.core.money import D, q
from app.core.security import generate_token
from app.models import Cart, CartItem, Coupon, CouponRedemption, Order, ProductVariant, User
from app.services import catalog_service
from app.services.common import get_setting
from app.services.pricing import CouponRule, PriceLine, PricingResult, PromoRule, ShippingInput, price_cart


# ---------------------------------------------------------------- cart lifecycle
def get_cart(db: Session, user: User | None, token: str | None, create: bool = True) -> Cart | None:
    cart = None
    if user:
        cart = db.scalar(select(Cart).where(Cart.user_id == user.id, Cart.status == "active").order_by(Cart.id.desc()))
    if cart is None and token:
        cart = db.scalar(select(Cart).where(Cart.token == token, Cart.status == "active"))
        if cart and cart.user_id and (not user or cart.user_id != user.id):
            cart = None  # a token can't be used to read another user's cart
        if cart and user and cart.user_id is None:
            cart.user_id = user.id
    if cart is None and create:
        cart = Cart(token=generate_token(24), user_id=user.id if user else None, status="active")
        db.add(cart)
        db.flush()
    return cart


def merge_guest_cart(db: Session, user: User, token: str | None) -> None:
    if not token:
        return
    guest = db.scalar(select(Cart).where(Cart.token == token, Cart.status == "active", Cart.user_id.is_(None)))
    if not guest:
        return
    mine = db.scalar(select(Cart).where(Cart.user_id == user.id, Cart.status == "active").order_by(Cart.id.desc()))
    if mine is None:
        guest.user_id = user.id
        return
    for gi in guest.items:
        existing = next((i for i in mine.items if i.variant_id == gi.variant_id), None)
        max_q = gi.variant.product.max_order_qty
        if existing:
            existing.quantity = min(max_q, existing.quantity + gi.quantity)
        else:
            mine.items.append(CartItem(variant_id=gi.variant_id, quantity=min(max_q, gi.quantity), price_at_add=gi.price_at_add))
    if guest.coupon_code and not mine.coupon_code:
        mine.coupon_code = guest.coupon_code
    guest.status = "merged"
    db.flush()


def _sellable_variant(db: Session, variant_id: int) -> ProductVariant:
    v = db.get(ProductVariant, variant_id)
    if not v or not v.is_active or v.product.status != "active":
        raise NotFound("This product is no longer available", code="variant_unavailable")
    return v


def add_item(db: Session, cart: Cart, variant_id: int, quantity: int) -> CartItem:
    v = _sellable_variant(db, variant_id)
    p = v.product
    existing = next((i for i in cart.items if i.variant_id == variant_id), None)
    new_qty = quantity + (existing.quantity if existing else 0)
    _validate_qty(v, new_qty)
    if existing:
        existing.quantity = new_qty
        item = existing
    else:
        item = CartItem(variant_id=v.id, quantity=new_qty, price_at_add=catalog_service.variant_price(v))
        cart.items.append(item)
    cart.updated_at = utcnow()
    db.flush()
    return item


def _validate_qty(v: ProductVariant, qty: int) -> None:
    p = v.product
    if qty < p.min_order_qty:
        raise ValidationFailed(f"Minimum quantity for this item is {p.min_order_qty}", code="below_min_qty")
    if qty > p.max_order_qty:
        raise ValidationFailed(f"You can buy at most {p.max_order_qty} of this item per order", code="above_max_qty")
    avail = v.inventory.available if v.inventory else 0
    if avail <= 0:
        raise ValidationFailed("This item is out of stock", code="out_of_stock")
    if qty > avail:
        raise ValidationFailed(f"Only {avail} left in stock", code="insufficient_stock", details={"available": avail})


def update_item(db: Session, cart: Cart, item_id: int, quantity: int) -> None:
    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        raise NotFound("Cart item not found")
    v = _sellable_variant(db, item.variant_id)
    _validate_qty(v, quantity)
    item.quantity = quantity
    db.flush()


def remove_item(db: Session, cart: Cart, item_id: int) -> None:
    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        raise NotFound("Cart item not found")
    cart.items.remove(item)
    db.flush()


# ---------------------------------------------------------------- coupons & promotions
def coupon_rule(db: Session, code: str, user: User | None, email: str | None) -> tuple[CouponRule | None, str | None, Coupon | None]:
    code = code.strip().upper()
    c = db.scalar(select(Coupon).where(func.upper(Coupon.code) == code))
    if not c or not c.is_active:
        return None, f"Coupon {code} is not valid.", None
    now = utcnow()
    if c.starts_at and c.starts_at > now:
        return None, f"Coupon {code} is not active yet.", c
    if c.ends_at and c.ends_at <= now:
        return None, f"Coupon {code} has expired.", c
    if c.usage_limit_total is not None and c.times_used >= c.usage_limit_total:
        return None, f"Coupon {code} has reached its usage limit.", c
    who = (user.email if user else email or "").lower()
    if c.customer_emails and who not in [e.lower() for e in c.customer_emails]:
        return None, f"Coupon {code} is not available for your account.", c
    if c.usage_limit_per_user is not None and who:
        used = db.scalar(
            select(func.count(CouponRedemption.id)).where(
                CouponRedemption.coupon_id == c.id, CouponRedemption.status == "applied", func.lower(CouponRedemption.email) == who
            )
        )
        if used >= c.usage_limit_per_user:
            return None, f"You've already used coupon {code}.", c
    if c.first_order_only:
        if not who:
            return None, f"Log in or enter your email to use first-order coupon {code}.", c
        prior = db.scalar(
            select(func.count(Order.id)).where(
                func.lower(Order.email) == who, Order.status.not_in(["cancelled", "payment_pending"])
            )
        )
        if prior:
            return None, f"{code} is valid on your first order only.", c
    rule = CouponRule(
        id=c.id, code=c.code, discount_type=c.discount_type, value=D(c.value), min_cart_value=D(c.min_cart_value),
        max_discount=D(c.max_discount) if c.max_discount is not None else None, applies_to=c.applies_to,
        category_ids=list(c.category_ids or []), product_ids=list(c.product_ids or []),
        combinable_with_promotions=c.combinable_with_promotions,
    )
    return rule, None, c


def promo_rules(db: Session) -> list[PromoRule]:
    return [
        PromoRule(
            id=p.id, name=p.name, promo_type=p.promo_type, value=D(p.value), config=dict(p.config or {}),
            applies_to=p.applies_to, category_ids=list(p.category_ids or []), product_ids=list(p.product_ids or []),
            priority=p.priority, is_stackable=p.is_stackable, badge_text=p.badge_text,
        )
        for p in catalog_service.active_promotions(db)
    ]


# ---------------------------------------------------------------- pricing a cart
@dataclass
class CartIssue:
    item_id: int
    code: str
    message: str


def build_lines(db: Session, cart: Cart) -> tuple[list[PriceLine], list[CartIssue]]:
    lines, issues = [], []
    for it in cart.items:
        v = it.variant
        p = v.product
        if not v.is_active or p.status != "active":
            issues.append(CartIssue(it.id, "unavailable", f"{p.name} is no longer available."))
            continue
        avail = v.inventory.available if v.inventory else 0
        if avail <= 0:
            issues.append(CartIssue(it.id, "out_of_stock", f"{p.name} ({v.name}) is out of stock."))
            continue
        if it.quantity > avail:
            issues.append(CartIssue(it.id, "insufficient_stock", f"Only {avail} of {p.name} ({v.name}) available."))
        if it.quantity > p.max_order_qty:
            issues.append(CartIssue(it.id, "above_max_qty", f"Max {p.max_order_qty} per order for {p.name}."))
        if it.quantity < p.min_order_qty:
            issues.append(CartIssue(it.id, "below_min_qty", f"Min {p.min_order_qty} required for {p.name}."))
        price = catalog_service.variant_price(v)
        if q(it.price_at_add) != price:
            direction = "dropped" if price < it.price_at_add else "changed"
            issues.append(CartIssue(it.id, "price_changed", f"Price of {p.name} has {direction} to ₹{price}."))
        lines.append(
            PriceLine(
                key=str(it.id), variant_id=v.id, product_id=p.id,
                category_ids=catalog_service.category_ancestor_ids(p.category), quantity=it.quantity,
                unit_mrp=q(v.mrp), unit_price=price, tax_rate=D(p.tax_rate.rate) if p.tax_rate else D(0), name=p.name,
            )
        )
    return lines, issues


def price(db: Session, cart: Cart, *, user: User | None, email: str | None = None, coupon_code: str | None = None,
          shipping_method_id: int | None = None, payment_method: str = "razorpay") -> tuple[PricingResult, list[CartIssue]]:
    from app.services import shipping_service

    lines, issues = build_lines(db, cart)
    code = coupon_code if coupon_code is not None else cart.coupon_code
    rule, err = None, None
    if code:
        rule, err, _ = coupon_rule(db, code, user, email)
        if rule is None:
            rule = CouponRule(0, code.upper(), "fixed", D(0), D(0), None, "all", [], [], True)
    method = None
    try:
        method = shipping_service.get_method(db, shipping_method_id)
    except NotFound:
        method = None
    ship = ShippingInput(method.id, method.name, D(method.base_charge),
                         D(method.free_shipping_threshold) if method.free_shipping_threshold is not None else None) if method else None
    result = price_cart(
        lines,
        promotions=promo_rules(db),
        coupon=rule,
        coupon_error=err,
        shipping=ship,
        store_free_threshold=D(get_setting(db, "free_shipping_threshold", "999")),
        allow_coupon_with_promotions=bool(get_setting(db, "allow_coupon_with_promotions", True)),
        cod=payment_method == "cod",
        cod_fee=D(get_setting(db, "cod_fee", "49")),
    )
    return result, issues


def money(v: Decimal | None) -> str | None:
    return None if v is None else f"{q(v):.2f}"


def serialize_totals(r: PricingResult) -> dict:
    return {
        "subtotal_mrp": money(r.subtotal_mrp),
        "subtotal": money(r.subtotal),
        "item_discount": money(r.item_discount),
        "promotion_discount": money(r.promotion_discount),
        "coupon_discount": money(r.coupon_discount),
        "shipping_charge": money(r.shipping_charge),
        "cod_charge": money(r.cod_charge),
        "tax_total": money(r.tax_total),
        "grand_total": money(r.grand_total),
        "total_savings": money(r.total_savings),
        "free_shipping": r.free_shipping,
        "free_shipping_threshold": money(r.free_shipping_threshold),
        "amount_to_free_shipping": money(r.amount_to_free_shipping),
        "applied_promotions": r.applied_promotions,
        "coupon": {"code": r.coupon_code, "applied": r.coupon_applied, "message": r.coupon_message} if r.coupon_code else None,
        "messages": r.messages,
        "tax_inclusive": True,
    }


def serialize_cart(db: Session, cart: Cart, user: User | None) -> dict:
    result, issues = price(db, cart, user=user)
    by_key = {ln.key: ln for ln in result.lines}
    items = []
    for it in cart.items:
        v = it.variant
        p = v.product
        ln = by_key.get(str(it.id))
        img = next((i.url for i in p.images if i.variant_id == v.id), None) or (catalog_service._primary_images(p)[0])
        avail = v.inventory.available if v.inventory else 0
        unit_price = catalog_service.variant_price(v)
        items.append({
            "id": it.id,
            "variant_id": v.id,
            "product_id": p.id,
            "product_slug": p.slug,
            "product_name": p.name,
            "variant_name": v.name,
            "sku": v.sku,
            "image": img,
            "attributes": {av.attribute.name: av.value for av in v.attribute_values if av.attribute.is_variant_axis},
            "quantity": it.quantity,
            "unit_mrp": money(v.mrp),
            "unit_price": money(unit_price),
            "line_mrp": money(v.mrp * it.quantity),
            "line_subtotal": money(unit_price * it.quantity),
            "promo_discount": money(ln.promo_discount) if ln else "0.00",
            "coupon_discount": money(ln.coupon_discount) if ln else "0.00",
            "line_total": money(ln.net) if ln else "0.00",
            "available": avail,
            "min_qty": p.min_order_qty,
            "max_qty": min(p.max_order_qty, max(avail, 0)),
            "purchasable": ln is not None,
        })
    return {
        "id": cart.id,
        "token": cart.token,
        "item_count": sum(i.quantity for i in cart.items),
        "items": items,
        "totals": serialize_totals(result),
        "issues": [{"item_id": i.item_id, "code": i.code, "message": i.message} for i in issues],
        "can_checkout": bool(result.lines) and not any(i.code in ("insufficient_stock", "above_max_qty", "below_min_qty") for i in issues)
        and len(result.lines) == len(cart.items),
    }
