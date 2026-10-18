"""Pricing engine.

Order of application (documented in docs/ARCHITECTURE.md (Pricing engine)):
  1. Item price      — effective sale price per variant (scheduled sale price when its window is active).
  2. Promotions      — automatic, ascending `priority`. Each promotion discounts the *current net* of its
                       eligible lines. If a promotion that actually discounts something is non-stackable,
                       no further item-level promotions are evaluated. Free-shipping promotions only
                       affect shipping and are evaluated independently.
  3. Coupon          — at most one coupon per order. Applied to the post-promotion net of eligible lines.
                       If the coupon is not combinable with promotions (or the store disallows stacking)
                       and promotions applied, the engine keeps whichever is better for the customer and
                       says so in `messages`.
  4. Shipping        — free when the post-discount merchandise total reaches the threshold, or when a
                       free-shipping coupon/promotion applies; otherwise the method's base charge.
  5. COD fee         — flat fee for cash-on-delivery orders.
  6. Tax (GST)       — prices are tax-inclusive (Indian MRP convention). The GST component of each line's
                       net amount is reported; it is not added on top.
All amounts are Decimal, quantized to paise, and computed on the server only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.core.money import ZERO, D, allocate, q, tax_from_inclusive


@dataclass
class PriceLine:
    key: str  # stable id (cart item id / variant id)
    variant_id: int
    product_id: int
    category_ids: list[int]  # category + its ancestors
    quantity: int
    unit_mrp: Decimal
    unit_price: Decimal
    tax_rate: Decimal = ZERO
    name: str = ""
    # outputs
    promo_discount: Decimal = ZERO
    coupon_discount: Decimal = ZERO

    @property
    def line_mrp(self) -> Decimal:
        return q(self.unit_mrp * self.quantity)

    @property
    def line_subtotal(self) -> Decimal:
        return q(self.unit_price * self.quantity)

    @property
    def net(self) -> Decimal:
        return q(self.line_subtotal - self.promo_discount - self.coupon_discount)

    @property
    def tax(self) -> Decimal:
        return tax_from_inclusive(self.net, self.tax_rate)


@dataclass
class PromoRule:
    id: int
    name: str
    promo_type: str  # percent_off | fixed_off | bogo | quantity_discount | free_shipping
    value: Decimal
    config: dict
    applies_to: str
    category_ids: list[int]
    product_ids: list[int]
    priority: int
    is_stackable: bool
    badge_text: str | None = None


@dataclass
class CouponRule:
    id: int
    code: str
    discount_type: str  # percent | fixed | free_shipping
    value: Decimal
    min_cart_value: Decimal
    max_discount: Decimal | None
    applies_to: str
    category_ids: list[int]
    product_ids: list[int]
    combinable_with_promotions: bool


@dataclass
class ShippingInput:
    method_id: int | None
    method_name: str
    base_charge: Decimal
    free_threshold: Decimal | None


@dataclass
class PricingResult:
    lines: list[PriceLine]
    subtotal_mrp: Decimal
    subtotal: Decimal
    item_discount: Decimal
    promotion_discount: Decimal
    coupon_discount: Decimal
    shipping_charge: Decimal
    cod_charge: Decimal
    tax_total: Decimal
    grand_total: Decimal
    applied_promotions: list[dict] = field(default_factory=list)
    coupon_code: str | None = None
    coupon_applied: bool = False
    coupon_message: str | None = None
    free_shipping: bool = False
    free_shipping_threshold: Decimal | None = None
    amount_to_free_shipping: Decimal = ZERO
    messages: list[str] = field(default_factory=list)

    @property
    def merchandise_net(self) -> Decimal:
        return q(self.subtotal - self.promotion_discount - self.coupon_discount)

    @property
    def total_savings(self) -> Decimal:
        return q(self.item_discount + self.promotion_discount + self.coupon_discount)


def effective_unit_price(sale_price, scheduled_price, starts_at: datetime | None, ends_at: datetime | None, now: datetime) -> Decimal:
    if scheduled_price is not None and starts_at and starts_at <= now and (ends_at is None or now < ends_at):
        return q(scheduled_price)
    return q(sale_price)


def _eligible(lines: list[PriceLine], applies_to: str, cat_ids: list[int], prod_ids: list[int]) -> list[PriceLine]:
    if applies_to == "categories":
        s = set(cat_ids or [])
        return [ln for ln in lines if s.intersection(ln.category_ids)]
    if applies_to == "products":
        s = set(prod_ids or [])
        return [ln for ln in lines if ln.product_id in s]
    return list(lines)


def _promo_amount(rule: PromoRule, elig: list[PriceLine], cart_subtotal: Decimal) -> tuple[Decimal, dict[str, Decimal]]:
    """Returns (total, per-line allocation) for one item-level promotion."""
    cfg = rule.config or {}
    if not elig:
        return ZERO, {}
    if D(cfg.get("min_cart_value", 0)) > cart_subtotal:
        return ZERO, {}
    nets = [max(ZERO, ln.net) for ln in elig]
    pool = sum(nets, ZERO)
    if pool <= 0:
        return ZERO, {}

    total = ZERO
    if rule.promo_type == "percent_off":
        total = q(pool * rule.value / 100)
    elif rule.promo_type == "fixed_off":
        total = min(q(rule.value), pool)
    elif rule.promo_type == "quantity_discount":
        if sum(ln.quantity for ln in elig) >= int(cfg.get("min_qty", 2)):
            total = q(pool * rule.value / 100)
    elif rule.promo_type == "bogo":
        buy, get = int(cfg.get("buy_qty", 1)), int(cfg.get("get_qty", 1))
        pct = D(cfg.get("get_discount_pct", 100))
        # Expand to units at their current net unit value; the cheapest units are the "get" units.
        units: list[tuple[Decimal, str]] = []
        for ln in elig:
            unit_net = q(max(ZERO, ln.net) / ln.quantity)
            units += [(unit_net, ln.key)] * ln.quantity
        free_units = (len(units) // (buy + get)) * get
        units.sort(key=lambda u: u[0])
        per_line: dict[str, Decimal] = {}
        for unit_net, key in units[:free_units]:
            amt = q(unit_net * pct / 100)
            per_line[key] = q(per_line.get(key, ZERO) + amt)
        total = sum(per_line.values(), ZERO)
        return total, per_line
    else:
        return ZERO, {}

    cap = cfg.get("max_discount")
    if cap is not None:
        total = min(total, q(cap))
    if total <= 0:
        return ZERO, {}
    parts = allocate(total, nets)
    return total, {ln.key: p for ln, p in zip(elig, parts)}


def _apply_promotions(lines: list[PriceLine], promos: list[PromoRule], subtotal: Decimal) -> tuple[list[dict], bool]:
    applied: list[dict] = []
    free_ship = False
    for rule in sorted(promos, key=lambda r: (r.priority, r.id)):
        if rule.promo_type == "free_shipping":
            continue
        elig = _eligible(lines, rule.applies_to, rule.category_ids, rule.product_ids)
        total, per_line = _promo_amount(rule, elig, subtotal)
        if total <= 0:
            continue
        for ln in lines:
            if ln.key in per_line:
                ln.promo_discount = q(ln.promo_discount + per_line[ln.key])
        applied.append({"id": rule.id, "name": rule.name, "type": rule.promo_type, "amount": str(total), "badge": rule.badge_text})
        if not rule.is_stackable:
            break
    for rule in promos:
        if rule.promo_type == "free_shipping":
            elig = _eligible(lines, rule.applies_to, rule.category_ids, rule.product_ids)
            if elig and subtotal >= D((rule.config or {}).get("min_cart_value", 0)):
                free_ship = True
                applied.append({"id": rule.id, "name": rule.name, "type": "free_shipping", "amount": "0.00", "badge": rule.badge_text})
    return applied, free_ship


def _coupon_amount(c: CouponRule, lines: list[PriceLine]) -> tuple[Decimal, dict[str, Decimal], str | None]:
    elig = _eligible(lines, c.applies_to, c.category_ids, c.product_ids)
    if not elig:
        return ZERO, {}, "This coupon doesn't apply to the items in your cart."
    nets = [max(ZERO, ln.net) for ln in elig]
    pool = sum(nets, ZERO)
    if c.discount_type == "free_shipping":
        return ZERO, {}, None
    if c.discount_type == "percent":
        total = q(pool * c.value / 100)
        if c.max_discount is not None:
            total = min(total, q(c.max_discount))
    else:
        total = min(q(c.value), pool)
    parts = allocate(total, nets)
    return total, {ln.key: p for ln, p in zip(elig, parts)}, None


def price_cart(
    lines: list[PriceLine],
    *,
    promotions: list[PromoRule],
    coupon: CouponRule | None,
    coupon_error: str | None,
    shipping: ShippingInput | None,
    store_free_threshold: Decimal | None,
    allow_coupon_with_promotions: bool,
    cod: bool,
    cod_fee: Decimal,
) -> PricingResult:
    for ln in lines:
        ln.promo_discount = ZERO
        ln.coupon_discount = ZERO
    messages: list[str] = []
    subtotal_mrp = q(sum((ln.line_mrp for ln in lines), ZERO))
    subtotal = q(sum((ln.line_subtotal for ln in lines), ZERO))

    applied, promo_free_ship = _apply_promotions(lines, promotions, subtotal)
    promo_total = q(sum((ln.promo_discount for ln in lines), ZERO))

    coupon_applied = False
    coupon_free_ship = False
    coupon_msg = coupon_error
    coupon_code = coupon.code if coupon else None
    if coupon and not coupon_error:
        if subtotal < coupon.min_cart_value:
            coupon_msg = f"Add items worth ₹{q(coupon.min_cart_value - subtotal)} more to use {coupon.code}."
        else:
            stack_ok = allow_coupon_with_promotions and coupon.combinable_with_promotions
            item_promos_applied = promo_total > 0
            if not stack_ok and item_promos_applied:
                # Evaluate coupon alone (no item promotions) and keep the better outcome for the customer.
                snapshot = {ln.key: ln.promo_discount for ln in lines}
                for ln in lines:
                    ln.promo_discount = ZERO
                c_total, _, err = _coupon_amount(coupon, lines)
                if err is None and c_total > promo_total:
                    applied = [a for a in applied if a["type"] == "free_shipping"]
                    promo_total = ZERO
                    messages.append(f"{coupon.code} can't be combined with automatic offers; we applied the better deal.")
                else:
                    for ln in lines:
                        ln.promo_discount = snapshot[ln.key]
                    coupon_msg = (
                        err or f"{coupon.code} can't be combined with the offers already applied, which save you more."
                    )
                    coupon = None
            if coupon:
                c_total, per_line, err = _coupon_amount(coupon, lines)
                if err:
                    coupon_msg = err
                else:
                    for ln in lines:
                        if ln.key in per_line:
                            ln.coupon_discount = per_line[ln.key]
                    coupon_applied = True
                    coupon_free_ship = coupon.discount_type == "free_shipping"
                    coupon_msg = f"{coupon.code} applied."

    promo_total = q(sum((ln.promo_discount for ln in lines), ZERO))
    coupon_total = q(sum((ln.coupon_discount for ln in lines), ZERO))
    merch_net = q(subtotal - promo_total - coupon_total)

    threshold = None
    if shipping:
        threshold = shipping.free_threshold if shipping.free_threshold is not None else store_free_threshold
    free_ship = promo_free_ship or coupon_free_ship or (threshold is not None and merch_net >= threshold)
    shipping_charge = ZERO if (free_ship or not shipping or not lines) else q(shipping.base_charge)
    to_free = ZERO if (free_ship or threshold is None) else q(max(ZERO, threshold - merch_net))

    cod_charge = q(cod_fee) if (cod and lines) else ZERO
    tax_total = q(sum((ln.tax for ln in lines), ZERO))
    grand = q(merch_net + shipping_charge + cod_charge)

    return PricingResult(
        lines=lines,
        subtotal_mrp=subtotal_mrp,
        subtotal=subtotal,
        item_discount=q(subtotal_mrp - subtotal),
        promotion_discount=promo_total,
        coupon_discount=coupon_total,
        shipping_charge=shipping_charge,
        cod_charge=cod_charge,
        tax_total=tax_total,
        grand_total=grand,
        applied_promotions=applied,
        coupon_code=coupon_code,
        coupon_applied=coupon_applied,
        coupon_message=coupon_msg,
        free_shipping=bool(free_ship and lines),
        free_shipping_threshold=threshold,
        amount_to_free_shipping=to_free,
        messages=messages,
    )
