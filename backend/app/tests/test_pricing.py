"""Pure unit tests of the pricing engine (no database, no HTTP)."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.services.pricing import CouponRule, PriceLine, PromoRule, ShippingInput, effective_unit_price, price_cart

D = Decimal
STANDARD = ShippingInput(method_id=1, method_name="Standard", base_charge=D("79.00"), free_threshold=None)


def line(key="a", qty=1, mrp="1000.00", price="1000.00", product_id=1, cats=(10,), tax="0") -> PriceLine:
    return PriceLine(key=key, variant_id=hash(key) % 1000, product_id=product_id, category_ids=list(cats), quantity=qty,
                     unit_mrp=D(mrp), unit_price=D(price), tax_rate=D(tax), name=key)


def promo(pid=1, promo_type="percent_off", value="10", config=None, applies_to="all", cats=(), prods=(), priority=100,
          stackable=True) -> PromoRule:
    return PromoRule(id=pid, name=f"P{pid}", promo_type=promo_type, value=D(value), config=config or {}, applies_to=applies_to,
                     category_ids=list(cats), product_ids=list(prods), priority=priority, is_stackable=stackable)


def coupon(code="SAVE", discount_type="percent", value="10", min_cart="0", max_discount=None, applies_to="all", cats=(),
           prods=(), combinable=True) -> CouponRule:
    return CouponRule(id=1, code=code, discount_type=discount_type, value=D(value), min_cart_value=D(min_cart),
                      max_discount=D(max_discount) if max_discount is not None else None, applies_to=applies_to,
                      category_ids=list(cats), product_ids=list(prods), combinable_with_promotions=combinable)


def run(lines, *, promotions=(), cpn=None, coupon_error=None, shipping=STANDARD, threshold="999", allow=True, cod=False, cod_fee="49"):
    return price_cart(list(lines), promotions=list(promotions), coupon=cpn, coupon_error=coupon_error, shipping=shipping,
                      store_free_threshold=D(threshold) if threshold is not None else None,
                      allow_coupon_with_promotions=allow, cod=cod, cod_fee=D(cod_fee))


# ----------------------------------------------------------------------------- item prices
def test_mrp_vs_sale_price_discount():
    r = run([line(qty=2, mrp="1299.00", price="899.00")])
    assert r.subtotal_mrp == D("2598.00")
    assert r.subtotal == D("1798.00")
    assert r.item_discount == D("800.00")
    assert r.total_savings == D("800.00")
    assert r.grand_total == D("1798.00")  # above the free-shipping threshold


@pytest.mark.parametrize(
    "starts,ends,expected",
    [
        (timedelta(days=-1), timedelta(days=1), "799.00"),   # window active
        (timedelta(days=1), timedelta(days=2), "899.00"),    # not started yet
        (timedelta(days=-2), timedelta(days=-1), "899.00"),  # already ended
        (timedelta(days=-1), None, "799.00"),                # open-ended window
        (timedelta(days=-1), timedelta(0), "899.00"),        # end is exclusive
    ],
)
def test_scheduled_sale_price_window(starts, ends, expected):
    now = datetime(2026, 10, 18, 12, 0, 0)
    got = effective_unit_price(D("899"), D("799"), now + starts, (now + ends) if ends is not None else None, now)
    assert got == D(expected)
    assert isinstance(got, Decimal)


def test_scheduled_price_ignored_without_start_date():
    now = datetime(2026, 10, 18)
    assert effective_unit_price(D("899"), D("799"), None, None, now) == D("899.00")


# ----------------------------------------------------------------------------- coupons
def test_percent_coupon_respects_max_discount_cap():
    r = run([line(price="2000.00", mrp="2000.00")], cpn=coupon(value="20", max_discount="300"))
    assert r.coupon_applied
    assert r.coupon_discount == D("300.00")
    assert r.grand_total == D("1700.00")


def test_percent_coupon_below_cap():
    r = run([line(price="1000.00")], cpn=coupon(value="20", max_discount="300"))
    assert r.coupon_discount == D("200.00")


def test_fixed_coupon_is_capped_at_eligible_total():
    lines = [line("cheap", price="300.00", product_id=7), line("other", price="2000.00", product_id=8)]
    r = run(lines, cpn=coupon(discount_type="fixed", value="500", applies_to="products", prods=[7]))
    assert r.coupon_applied
    assert r.coupon_discount == D("300.00")
    by_key = {ln.key: ln for ln in r.lines}
    assert by_key["cheap"].coupon_discount == D("300.00")
    assert by_key["other"].coupon_discount == D("0.00")


def test_category_specific_coupon_only_discounts_matching_lines():
    lines = [line("ear", price="1000.00", cats=(11, 1)), line("kurti", price="1000.00", cats=(21, 2))]
    r = run(lines, cpn=coupon(value="10", applies_to="categories", cats=[1]))  # ancestor category id
    by_key = {ln.key: ln for ln in r.lines}
    assert by_key["ear"].coupon_discount == D("100.00")
    assert by_key["kurti"].coupon_discount == D("0.00")
    assert r.coupon_discount == D("100.00")


def test_product_specific_coupon_not_applicable_to_cart():
    r = run([line(product_id=1)], cpn=coupon(applies_to="products", prods=[99]))
    assert not r.coupon_applied
    assert r.coupon_discount == D("0.00")
    assert "doesn't apply" in r.coupon_message


def test_coupon_min_cart_value_message():
    r = run([line(price="500.00", mrp="500.00")], cpn=coupon(code="BIG", min_cart="999"))
    assert not r.coupon_applied
    assert r.coupon_discount == D("0.00")
    assert r.coupon_message == "Add items worth ₹499.00 more to use BIG."


def test_coupon_error_passed_through():
    r = run([line()], cpn=coupon(code="OLD"), coupon_error="Coupon OLD has expired.")
    assert not r.coupon_applied
    assert r.coupon_message == "Coupon OLD has expired."


# ----------------------------------------------------------------------------- shipping & fees
def test_shipping_charged_below_threshold_and_amount_to_free_shipping():
    r = run([line(price="500.00", mrp="500.00")])
    assert r.shipping_charge == D("79.00")
    assert not r.free_shipping
    assert r.amount_to_free_shipping == D("499.00")
    assert r.free_shipping_threshold == D("999")
    assert r.grand_total == D("579.00")


def test_free_shipping_when_threshold_reached():
    r = run([line(price="999.00", mrp="999.00")])
    assert r.shipping_charge == D("0.00")
    assert r.free_shipping
    assert r.amount_to_free_shipping == D("0.00")


def test_threshold_uses_post_discount_total():
    r = run([line(price="1000.00")], cpn=coupon(discount_type="fixed", value="100"))
    assert r.merchandise_net == D("900.00")
    assert r.shipping_charge == D("79.00")
    assert r.amount_to_free_shipping == D("99.00")


def test_method_threshold_overrides_store_default():
    ship = ShippingInput(2, "Express", D("149.00"), D("2999.00"))
    r = run([line(price="1500.00")], shipping=ship)
    assert r.shipping_charge == D("149.00")
    assert r.amount_to_free_shipping == D("1499.00")


def test_free_shipping_coupon():
    r = run([line(price="300.00", mrp="300.00")], cpn=coupon(code="FREESHIP", discount_type="free_shipping", value="0"))
    assert r.coupon_applied
    assert r.coupon_discount == D("0.00")
    assert r.shipping_charge == D("0.00")
    assert r.free_shipping
    assert r.grand_total == D("300.00")


def test_free_shipping_promotion():
    r = run([line(price="300.00", cats=(5,))], promotions=[promo(promo_type="free_shipping", value="0", applies_to="categories", cats=[5])])
    assert r.shipping_charge == D("0.00")
    assert any(a["type"] == "free_shipping" for a in r.applied_promotions)


def test_cod_fee_added():
    r = run([line(price="500.00", mrp="500.00")], cod=True, cod_fee="49")
    assert r.cod_charge == D("49.00")
    assert r.grand_total == D("628.00")  # 500 + 79 shipping + 49 COD


def test_empty_cart_has_no_charges():
    r = run([], cod=True)
    assert r.grand_total == D("0.00")
    assert r.shipping_charge == D("0.00")
    assert r.cod_charge == D("0.00")


# ----------------------------------------------------------------------------- promotions
def test_bogo_cheapest_unit_is_free():
    lines = [line("big", qty=2, price="500.00", product_id=1), line("small", qty=1, price="300.00", product_id=2)]
    r = run(lines, promotions=[promo(promo_type="bogo", value="0", config={"buy_qty": 1, "get_qty": 1, "get_discount_pct": 100})])
    # 3 units -> one free unit, the cheapest (300)
    assert r.promotion_discount == D("300.00")
    by_key = {ln.key: ln for ln in r.lines}
    assert by_key["small"].promo_discount == D("300.00")
    assert by_key["big"].promo_discount == D("0.00")


def test_bogo_two_pairs():
    lines = [line("big", qty=2, price="500.00"), line("small", qty=2, price="300.00")]
    r = run(lines, promotions=[promo(promo_type="bogo", value="0", config={"buy_qty": 1, "get_qty": 1})])
    assert r.promotion_discount == D("600.00")


def test_bogo_single_unit_gets_nothing():
    r = run([line(qty=1, price="500.00")], promotions=[promo(promo_type="bogo", value="0", config={"buy_qty": 1, "get_qty": 1})])
    assert r.promotion_discount == D("0.00")
    assert r.applied_promotions == []


def test_quantity_discount_threshold():
    rule = promo(promo_type="quantity_discount", value="15", config={"min_qty": 3})
    below = run([line(qty=2, price="400.00")], promotions=[rule])
    assert below.promotion_discount == D("0.00")
    at = run([line(qty=3, price="400.00")], promotions=[rule])
    assert at.promotion_discount == D("180.00")  # 15% of 1200


def test_promotion_min_cart_value_and_max_discount():
    rule = promo(value="50", config={"min_cart_value": 1000, "max_discount": 100})
    assert run([line(price="900.00")], promotions=[rule]).promotion_discount == D("0.00")
    assert run([line(price="1000.00")], promotions=[rule]).promotion_discount == D("100.00")


def test_non_stackable_promotion_stops_later_promotions():
    first = promo(pid=1, value="10", priority=10, stackable=False)
    second = promo(pid=2, value="5", priority=20)
    r = run([line(price="1000.00")], promotions=[second, first])  # input order must not matter
    assert [a["id"] for a in r.applied_promotions] == [1]
    assert r.promotion_discount == D("100.00")


def test_stackable_promotions_compound_on_current_net():
    first = promo(pid=1, value="10", priority=10, stackable=True)
    second = promo(pid=2, value="5", priority=20)
    r = run([line(price="1000.00")], promotions=[first, second])
    assert [a["id"] for a in r.applied_promotions] == [1, 2]
    assert r.promotion_discount == D("145.00")  # 100 + 5% of 900


def test_non_stackable_promotion_that_does_not_apply_does_not_block():
    blocked = promo(pid=1, value="10", priority=10, stackable=False, applies_to="products", prods=[999])
    other = promo(pid=2, value="5", priority=20)
    r = run([line(price="1000.00")], promotions=[blocked, other])
    assert [a["id"] for a in r.applied_promotions] == [2]


# ----------------------------------------------------------------------------- coupon vs promotion conflicts
def test_non_combinable_coupon_wins_when_better():
    r = run([line(price="1000.00")], promotions=[promo(value="5")], cpn=coupon(value="10", combinable=False))
    assert r.coupon_applied
    assert r.coupon_discount == D("100.00")
    assert r.promotion_discount == D("0.00")
    assert r.applied_promotions == []
    assert any("better deal" in m for m in r.messages)


def test_non_combinable_coupon_rejected_when_promotion_is_better():
    r = run([line(price="1000.00")], promotions=[promo(value="20")], cpn=coupon(code="TEN", value="10", combinable=False))
    assert not r.coupon_applied
    assert r.coupon_discount == D("0.00")
    assert r.promotion_discount == D("200.00")
    assert "can't be combined" in r.coupon_message


def test_store_setting_disallows_stacking_even_for_combinable_coupon():
    r = run([line(price="1000.00")], promotions=[promo(value="20")], cpn=coupon(value="10", combinable=True), allow=False)
    assert not r.coupon_applied
    assert r.promotion_discount == D("200.00")


def test_combinable_coupon_stacks_on_post_promotion_net():
    r = run([line(price="1000.00")], promotions=[promo(value="10")], cpn=coupon(value="10", combinable=True))
    assert r.promotion_discount == D("100.00")
    assert r.coupon_discount == D("90.00")
    assert r.grand_total == D("810.00") + D("79.00")


def test_non_combinable_coupon_keeps_free_shipping_promotion():
    lines = [line(price="500.00", cats=(5,))]
    promos = [promo(pid=1, value="5"), promo(pid=2, promo_type="free_shipping", value="0", applies_to="categories", cats=[5])]
    r = run(lines, promotions=promos, cpn=coupon(value="20", combinable=False))
    assert r.coupon_applied and r.coupon_discount == D("100.00")
    assert r.shipping_charge == D("0.00")
    assert [a["type"] for a in r.applied_promotions] == ["free_shipping"]


# ----------------------------------------------------------------------------- tax & precision
def test_tax_is_extracted_from_tax_inclusive_price():
    r = run([line(price="1030.00", mrp="1030.00", tax="3")])
    assert r.tax_total == D("30.00")
    assert r.grand_total == D("1030.00")  # tax is included, never added on top


def test_tax_computed_on_discounted_net():
    r = run([line(price="1030.00", tax="3")], cpn=coupon(discount_type="fixed", value="515"))
    assert r.lines[0].net == D("515.00")
    assert r.tax_total == D("15.00")


def test_zero_tax_rate():
    assert run([line(price="100.00", tax="0")]).tax_total == D("0.00")


def test_decimal_precision_and_exact_allocation():
    lines = [line(k, price="100.00", product_id=i) for i, k in enumerate(["a", "b", "c"])]
    r = run(lines, cpn=coupon(discount_type="fixed", value="100"))
    parts = [ln.coupon_discount for ln in r.lines]
    assert sum(parts) == D("100.00")
    assert sorted(parts) == [D("33.33"), D("33.33"), D("33.34")]
    assert sum(ln.net for ln in r.lines) == r.merchandise_net == D("200.00")
    for value in (r.subtotal, r.coupon_discount, r.grand_total, r.tax_total, r.shipping_charge, *parts):
        assert isinstance(value, Decimal)
        assert value.as_tuple().exponent == -2


def test_percent_rounding_is_half_up_to_paise():
    r = run([line(price="333.35")], cpn=coupon(value="10"))
    assert r.coupon_discount == D("33.34")  # 33.335 -> 33.34
    assert r.grand_total == D("300.01") + D("79.00")


def test_uneven_promo_allocation_sums_exactly():
    lines = [line("a", price="0.10"), line("b", price="0.10"), line("c", price="0.10")]
    r = run(lines, promotions=[promo(promo_type="fixed_off", value="0.10")], threshold=None)
    assert sum(ln.promo_discount for ln in r.lines) == D("0.10")
    assert r.promotion_discount == D("0.10")
