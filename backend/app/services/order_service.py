"""Order creation (checkout) and the order state machine."""
from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.money import D, q, to_paise
from app.models import (
    Address,
    Cart,
    Coupon,
    CouponRedemption,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
    Payment,
    ProductVariant,
    ReturnRequest,
    User,
)
from app.services import cart_service, catalog_service, inventory_service, shipping_service
from app.services.common import get_setting

# ------------------------------------------------------------------ state machine
STATUS_LABELS = {
    "order_placed": "Order Placed",
    "payment_pending": "Payment Pending",
    "payment_confirmed": "Payment Confirmed",
    "processing": "Processing",
    "packed": "Packed",
    "shipped": "Shipped",
    "out_for_delivery": "Out for Delivery",
    "delivered": "Delivered",
    "cancellation_requested": "Cancellation Requested",
    "cancelled": "Cancelled",
    "return_requested": "Return Requested",
    "returned": "Returned",
    "refund_initiated": "Refund Initiated",
    "refunded": "Refunded",
    "delivery_failed": "Delivery Failed",
}

TRANSITIONS: dict[str, set[str]] = {
    "order_placed": {"processing", "cancellation_requested", "cancelled"},  # COD orders start here
    "payment_pending": {"payment_confirmed", "cancelled"},
    "payment_confirmed": {"processing", "cancellation_requested", "cancelled"},
    "processing": {"packed", "cancellation_requested", "cancelled"},
    "packed": {"shipped", "cancellation_requested", "cancelled"},
    "shipped": {"out_for_delivery", "delivered", "delivery_failed"},
    "out_for_delivery": {"delivered", "delivery_failed"},
    "delivery_failed": {"shipped", "returned"},  # re-attempt or RTO (return to origin)
    "delivered": {"return_requested"},
    "cancellation_requested": {"cancelled", "processing", "packed", "payment_confirmed", "order_placed"},  # approve / reject
    "return_requested": {"returned", "delivered"},  # accept / reject
    "returned": {"refund_initiated"},
    "cancelled": {"refund_initiated"},
    "refund_initiated": {"refunded"},
    "refunded": set(),
}

# Statuses that admins may set directly from the order screen. Others are reached only through
# dedicated flows (payment verification, cancellation, returns, refunds) that enforce their side effects.
ADMIN_MANUAL_TARGETS = {"processing", "packed", "out_for_delivery", "delivered", "delivery_failed"}
CUSTOMER_CANCELLABLE = {"order_placed", "payment_pending", "payment_confirmed", "processing"}
CUSTOMER_CANCEL_REQUESTABLE = {"packed"}


def allowed_next(order: Order) -> list[str]:
    return sorted(TRANSITIONS.get(order.status, set()))


def transition(db: Session, order: Order, to: str, *, actor: User | None, note: str | None = None,
               actor_type: str = "admin", skip_side_effects: bool = False) -> None:
    frm = order.status
    if to == frm:
        return
    if to not in TRANSITIONS.get(frm, set()):
        raise Conflict(
            f"Cannot change order from '{STATUS_LABELS.get(frm, frm)}' to '{STATUS_LABELS.get(to, to)}'",
            code="invalid_transition", details={"from": frm, "to": to, "allowed": allowed_next(order)},
        )
    # Guards: business rules that the status alone cannot express.
    if to == "processing" and not (order.payment_status == "paid" or order.payment_method == "cod"):
        raise Conflict("Order cannot be processed until payment is confirmed", code="payment_required")
    if to == "shipped" and not any(s.tracking_number for s in order.shipments):
        raise Conflict("Add a shipment with a tracking number before marking as shipped", code="shipment_required")
    if to == "refund_initiated" and order.payment_status not in ("paid", "partially_refunded", "refunded"):
        raise Conflict("Nothing to refund: order was never paid", code="not_paid")
    if to == "payment_confirmed" and order.payment_status != "paid":
        raise Conflict("Payment has not been verified", code="payment_required")
    if to in ("cancelled", "cancellation_requested"):
        order.previous_status = frm if to == "cancellation_requested" else order.previous_status
    if to == "return_requested":
        order.previous_status = frm
    order.status = to
    now = utcnow()
    if to == "cancelled":
        order.cancelled_at = now
    if to == "delivered":
        order.delivered_at = now
        for s in order.shipments:
            if s.status != "delivered":
                s.status, s.delivered_at = "delivered", now
        if order.payment_method == "cod" and order.payment_status != "paid":
            order.payment_status = "paid"
            order.paid_at = now
            for p in order.payments:
                if p.status == "cod_pending":
                    p.status, p.captured_at = "cod_collected", now
    db.add(OrderStatusHistory(order_id=order.id, from_status=frm, to_status=to, note=note,
                              actor_id=actor.id if actor else None, actor_type=actor_type))
    db.flush()


# ------------------------------------------------------------------ checkout
def _order_number(db: Session) -> str:
    for _ in range(10):
        n = f"{settings.ORDER_NUMBER_PREFIX}{utcnow():%y%m%d}{secrets.randbelow(10**5):05d}"
        if not db.scalar(select(Order.id).where(Order.order_number == n)):
            return n
    raise Conflict("Could not allocate an order number; please retry")


def _addr_from(model: Address | dict, kind: str) -> OrderAddress:
    get = (lambda k: getattr(model, k)) if isinstance(model, Address) else (lambda k: model.get(k))
    return OrderAddress(
        address_type=kind, full_name=get("full_name"), phone=get("phone"), line1=get("line1"), line2=get("line2"),
        landmark=get("landmark"), city=get("city"), state=get("state"), pin_code=get("pin_code"), country="IN",
        gstin=(model.get("gstin") if isinstance(model, dict) else None),
    )


def resolve_address(db: Session, user: User | None, address_id: int | None, address: dict | None) -> Address | dict:
    if address_id:
        if not user:
            raise ValidationFailed("Log in to use a saved address")
        a = db.get(Address, address_id)
        if not a or a.user_id != user.id:
            raise NotFound("Address not found")
        return a
    if not address:
        raise ValidationFailed("Shipping address is required", code="address_required")
    return address


def checkout_quote(db: Session, cart: Cart, *, user: User | None, email: str | None, pin: str | None,
                   shipping_method_id: int | None, payment_method: str, coupon_code: str | None) -> dict:
    result, issues = cart_service.price(db, cart, user=user, email=email, coupon_code=coupon_code,
                                        shipping_method_id=shipping_method_id, payment_method=payment_method)
    delivery = None
    cod_ok, cod_reason = True, None
    if pin:
        processing = max((it.variant.product.processing_days for it in cart.items), default=1)
        delivery = shipping_service.estimate(db, pin, processing, result.merchandise_net,
                                             D(get_setting(db, "free_shipping_threshold", "999")))
        if not delivery["serviceable"]:
            cod_ok, cod_reason = False, "PIN code not serviceable"
        elif not delivery["cod_available"]:
            cod_ok, cod_reason = False, "Cash on Delivery isn't available for this PIN code"
    if cod_ok and any(not it.variant.product.is_cod_available for it in cart.items):
        cod_ok, cod_reason = False, "Some items in your cart are not eligible for Cash on Delivery"
    cod_max = D(get_setting(db, "cod_max_order_value", "15000"))
    if cod_ok and result.merchandise_net > cod_max:
        cod_ok, cod_reason = False, f"Cash on Delivery is available for orders up to ₹{cod_max:,.0f}"
    if shipping_method_id and cod_ok:
        m = shipping_service.get_method(db, shipping_method_id)
        if not m.is_cod_allowed:
            cod_ok, cod_reason = False, f"Cash on Delivery isn't available with {m.name}"
    return {
        "totals": cart_service.serialize_totals(result),
        "issues": [{"item_id": i.item_id, "code": i.code, "message": i.message} for i in issues],
        "delivery": delivery,
        "cod_available": cod_ok,
        "cod_unavailable_reason": cod_reason,
        "cod_fee": f"{D(get_setting(db, 'cod_fee', '49')):.2f}",
        "_result": result,
        "_issues": issues,
    }


BLOCKING_ISSUES = {"unavailable", "out_of_stock", "insufficient_stock", "above_max_qty", "below_min_qty"}


def create_order(db: Session, *, cart: Cart, user: User | None, email: str, phone: str | None,
                 shipping_address: Address | dict, billing_address: Address | dict | None, shipping_method_id: int | None,
                 payment_method: str, coupon_code: str | None, customer_note: str | None, idempotency_key: str | None) -> tuple[Order, bool]:
    """Returns (order, created). All-or-nothing: runs inside the caller's transaction."""
    if idempotency_key:
        key = f"{user.id if user else 'g'}:{idempotency_key}"
        existing = db.scalar(select(Order).where(Order.idempotency_key == key))
        if existing:
            return existing, False
    else:
        key = None
    if not cart.items:
        raise ValidationFailed("Your cart is empty", code="empty_cart")
    if payment_method not in ("razorpay", "cod"):
        raise ValidationFailed("Unsupported payment method")

    ship_pin = shipping_address.pin_code if isinstance(shipping_address, Address) else shipping_address["pin_code"]
    rule = shipping_service.pin_rule(db, ship_pin)
    if not rule.serviceable:
        raise ValidationFailed("Sorry, we don't deliver to this PIN code yet.", code="pin_not_serviceable")
    method = shipping_service.get_method(db, shipping_method_id)

    quote = checkout_quote(db, cart, user=user, email=email, pin=ship_pin, shipping_method_id=method.id,
                           payment_method=payment_method, coupon_code=coupon_code)
    result, issues = quote["_result"], quote["_issues"]
    blocking = [i for i in issues if i.code in BLOCKING_ISSUES]
    if blocking or len(result.lines) != len(cart.items):
        raise Conflict("Some items in your cart need attention", code="cart_invalid",
                       details=[{"item_id": i.item_id, "code": i.code, "message": i.message} for i in issues])
    if payment_method == "cod" and not quote["cod_available"]:
        raise ValidationFailed(quote["cod_unavailable_reason"] or "COD not available", code="cod_unavailable")
    if coupon_code and not result.coupon_applied:
        raise ValidationFailed(result.coupon_message or "Coupon could not be applied", code="coupon_invalid")
    if result.grand_total < D("1.00") and payment_method == "razorpay":
        raise ValidationFailed("Order total must be at least ₹1", code="amount_too_low")

    processing = max(it.variant.product.processing_days for it in cart.items)
    dispatch, _, latest = shipping_service.estimate_dates(method, rule, processing)
    order = Order(
        order_number=_order_number(db), user_id=user.id if user else None, email=email.lower(), phone=phone,
        status="payment_pending" if payment_method == "razorpay" else "order_placed",
        payment_status="pending", payment_method=payment_method, currency=settings.PAYMENT_CURRENCY,
        subtotal_mrp=result.subtotal_mrp, subtotal=result.subtotal, item_discount_total=result.item_discount,
        promotion_discount=result.promotion_discount, coupon_discount=result.coupon_discount,
        coupon_code=result.coupon_code if result.coupon_applied else None, shipping_charge=result.shipping_charge,
        cod_charge=result.cod_charge, tax_total=result.tax_total, grand_total=result.grand_total,
        applied_promotions=result.applied_promotions, shipping_method_id=method.id, shipping_method_name=method.name,
        estimated_dispatch_date=dispatch, estimated_delivery_date=latest, idempotency_key=key,
        customer_note=customer_note,
    )
    db.add(order)
    by_key = {ln.key: ln for ln in result.lines}
    for it in cart.items:
        v: ProductVariant = it.variant
        p = v.product
        ln = by_key[str(it.id)]
        img = next((i.url for i in p.images if i.variant_id == v.id), None) or catalog_service._primary_images(p)[0]
        order.items.append(OrderItem(
            product_id=p.id, variant_id=v.id, product_name=p.name, product_slug=p.slug, variant_name=v.name, sku=v.sku,
            image_url=img, attributes={av.attribute.name: av.value for av in v.attribute_values},
            category_name=p.category.name, hsn_code=p.tax_rate.hsn_code if p.tax_rate else None,
            quantity=it.quantity, unit_mrp=ln.unit_mrp, unit_price=ln.unit_price,
            discount_amount=q(ln.promo_discount + ln.coupon_discount), tax_rate=ln.tax_rate, tax_amount=ln.tax,
            line_total=ln.net, unit_cost=v.cost_price,
        ))
    order.addresses.append(_addr_from(shipping_address, "shipping"))
    order.addresses.append(_addr_from(billing_address or shipping_address, "billing"))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if key:
            existing = db.scalar(select(Order).where(Order.idempotency_key == key))
            if existing:
                return existing, False
        raise

    wanted: dict[int, int] = {}
    for it in order.items:
        wanted[it.variant_id] = wanted.get(it.variant_id, 0) + it.quantity
    inventory_service.reserve(db, order, wanted)

    if order.coupon_code:
        _redeem_coupon(db, order, user)

    db.add(OrderStatusHistory(order_id=order.id, from_status=None, to_status=order.status,
                              note="Order created", actor_id=user.id if user else None, actor_type="customer"))
    if payment_method == "cod":
        db.add(Payment(order_id=order.id, provider="cod", mode="cod", method="cod", amount_paise=to_paise(order.grand_total),
                       currency=order.currency, status="cod_pending", attempts=0, amount_refunded_paise=0))
        inventory_service.commit(db, order)
    cart.status = "converted"
    db.flush()
    return order, True


def _redeem_coupon(db: Session, order: Order, user: User | None) -> None:
    c = db.scalar(select(Coupon).where(func.upper(Coupon.code) == order.coupon_code.upper()).with_for_update())
    if not c:
        raise ValidationFailed("Coupon no longer exists", code="coupon_invalid")
    if c.usage_limit_total is not None and c.times_used >= c.usage_limit_total:
        raise ValidationFailed(f"Coupon {c.code} has just reached its usage limit", code="coupon_exhausted")
    c.times_used += 1
    db.add(CouponRedemption(coupon_id=c.id, order_id=order.id, user_id=user.id if user else None, email=order.email,
                            discount_amount=order.coupon_discount, status="applied"))


def reverse_coupon(db: Session, order: Order) -> None:
    red = db.scalars(select(CouponRedemption).where(CouponRedemption.order_id == order.id, CouponRedemption.status == "applied")).all()
    for r in red:
        r.status = "reversed"
        c = db.scalar(select(Coupon).where(Coupon.id == r.coupon_id).with_for_update())
        if c and c.times_used > 0:
            c.times_used -= 1


# ------------------------------------------------------------------ cancellation
def cancel(db: Session, order: Order, *, actor: User | None, reason: str, actor_type: str) -> str:
    """Customer- or admin-initiated cancellation. Returns the resulting status."""
    if actor_type == "customer":
        if order.status in CUSTOMER_CANCEL_REQUESTABLE:
            transition(db, order, "cancellation_requested", actor=actor, note=reason, actor_type="customer")
            order.cancellation_reason = reason
            return order.status
        if order.status not in CUSTOMER_CANCELLABLE:
            raise Conflict("This order can no longer be cancelled. You can request a return after delivery.",
                           code="not_cancellable")
    elif order.status not in TRANSITIONS or "cancelled" not in TRANSITIONS[order.status]:
        raise Conflict(f"Orders that are '{STATUS_LABELS[order.status]}' cannot be cancelled", code="not_cancellable")

    committed = inventory_service.order_is_committed(db, order)
    transition(db, order, "cancelled", actor=actor, note=reason, actor_type=actor_type)
    order.cancellation_reason = reason
    inventory_service.release(db, order, "cancelled")
    if committed:
        inventory_service.restock_order(db, order, "cancellation", actor, note=f"Order {order.order_number} cancelled")
    reverse_coupon(db, order)
    for p in order.payments:
        if p.status in ("created", "cod_pending"):
            p.status = "cancelled"
    if order.payment_status == "paid":
        from app.services import payment_service

        payment_service.refund_order(db, order, amount=None, reason=f"Order cancelled: {reason}", actor=actor,
                                     idempotency_key=f"cancel:{order.id}")
    else:
        order.payment_status = "cancelled" if order.payment_status == "pending" else order.payment_status
    return order.status


def resolve_cancellation_request(db: Session, order: Order, approve: bool, actor: User, note: str | None) -> None:
    if order.status != "cancellation_requested":
        raise Conflict("No pending cancellation request")
    if approve:
        cancel(db, order, actor=actor, reason=order.cancellation_reason or note or "Approved by store", actor_type="admin")
    else:
        transition(db, order, order.previous_status or "processing", actor=actor, note=note or "Cancellation request declined")


# ------------------------------------------------------------------ returns
def request_return(db: Session, order: Order, user: User, items: list[dict], reason: str, details: str | None, return_type: str) -> ReturnRequest:
    if order.status != "delivered":
        raise Conflict("Returns can be requested only for delivered orders", code="not_returnable")
    from app.models import Product

    windows = [db.get(Product, it.product_id).return_window_days for it in order.items if it.product_id and db.get(Product, it.product_id)]
    window_days = max(windows or [int(get_setting(db, "return_window_days", 7))])
    if order.delivered_at and utcnow() > order.delivered_at + timedelta(days=window_days):
        raise Conflict(f"The {window_days}-day return window for this order has closed", code="return_window_closed")
    by_id = {it.id: it for it in order.items}
    clean = []
    for row in items:
        it = by_id.get(int(row["order_item_id"]))
        qty = int(row.get("quantity", 0))
        if not it or qty <= 0:
            raise ValidationFailed("Invalid return item")
        prod = db.get(Product, it.product_id) if it.product_id else None
        if prod and not prod.is_returnable:
            raise ValidationFailed(f"{it.product_name} is not eligible for return", code="item_not_returnable")
        if qty > it.quantity - it.returned_quantity:
            raise ValidationFailed(f"You can return at most {it.quantity - it.returned_quantity} of {it.product_name}")
        clean.append({"order_item_id": it.id, "quantity": qty})
    if not clean:
        raise ValidationFailed("Select at least one item to return")
    refund_amount = q(sum(by_id[r["order_item_id"]].line_total / by_id[r["order_item_id"]].quantity * r["quantity"] for r in clean))
    rr = ReturnRequest(order_id=order.id, user_id=user.id, return_type=return_type, status="requested", reason=reason,
                       details=details, items=clean, refund_amount=refund_amount if return_type == "return" else D(0))
    db.add(rr)
    transition(db, order, "return_requested", actor=user, note=f"{return_type.title()} requested: {reason}", actor_type="customer")
    db.flush()
    return rr


def resolve_return(db: Session, rr: ReturnRequest, action: str, actor: User, note: str | None) -> ReturnRequest:
    """approve -> received (restock + refund) ; reject. Approved replacements ship a new unit manually."""
    order = rr.order
    if action == "reject":
        if rr.status not in ("requested", "approved"):
            raise Conflict("This return can no longer be rejected")
        rr.status, rr.admin_note, rr.resolved_at = "rejected", note, utcnow()
        if order.status == "return_requested":
            transition(db, order, "delivered", actor=actor, note=f"Return rejected: {note or ''}".strip())
        return rr
    if action == "approve":
        if rr.status != "requested":
            raise Conflict("Only new requests can be approved")
        rr.status, rr.admin_note = "approved", note
        return rr
    if action == "receive":
        if rr.status != "approved":
            raise Conflict("Approve the return before marking it received")
        qty_map = {r["order_item_id"]: r["quantity"] for r in rr.items}
        for it in order.items:
            if it.id in qty_map:
                it.returned_quantity += qty_map[it.id]
        inventory_service.restock_order(db, order, "return", actor, quantities=qty_map, note=f"Return #{rr.id}")
        rr.status = "received"
        transition(db, order, "returned", actor=actor, note=f"Return #{rr.id} received")
        if rr.return_type == "return" and rr.refund_amount and rr.refund_amount > 0:
            from app.services import payment_service

            refund = payment_service.refund_order(db, order, amount=rr.refund_amount, reason=f"Return #{rr.id}: {rr.reason}",
                                                  actor=actor, idempotency_key=f"return:{rr.id}")
            rr.refund_id = refund.id if refund else None
            rr.status = "refunded" if refund and refund.status == "processed" else "received"
        else:
            rr.status = "completed"
        rr.resolved_at = utcnow()
        return rr
    raise ValidationFailed("Unknown action")


def get_customer_order(db: Session, user: User, order_id: int | str) -> Order:
    stmt = select(Order).where(Order.user_id == user.id)
    stmt = stmt.where(Order.order_number == order_id) if isinstance(order_id, str) and not order_id.isdigit() else stmt.where(Order.id == int(order_id))
    order = db.scalar(stmt)
    if not order:
        raise NotFound("Order not found")
    return order


def assert_owner(order: Order, user: User) -> None:
    if order.user_id != user.id:
        raise Forbidden("Not your order")
