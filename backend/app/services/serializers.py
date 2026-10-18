from datetime import timedelta

from app.core.database import utcnow
from app.core.money import from_paise
from app.models import Order
from app.services.order_service import (
    CUSTOMER_CANCEL_REQUESTABLE,
    CUSTOMER_CANCELLABLE,
    STATUS_LABELS,
    allowed_next,
)

M = lambda v: None if v is None else f"{v:.2f}"  # noqa: E731

CUSTOMER_TIMELINE = ["order_placed", "payment_confirmed", "processing", "packed", "shipped", "out_for_delivery", "delivered"]


def address_dict(a) -> dict | None:
    if not a:
        return None
    return {k: getattr(a, k) for k in ("full_name", "phone", "line1", "line2", "landmark", "city", "state", "pin_code", "country", "gstin")}


def order_summary(o: Order) -> dict:
    return {
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status,
        "status_label": STATUS_LABELS.get(o.status, o.status),
        "payment_status": o.payment_status,
        "payment_method": o.payment_method,
        "grand_total": M(o.grand_total),
        "item_count": sum(i.quantity for i in o.items),
        "placed_at": o.placed_at.isoformat(),
        "estimated_delivery_date": o.estimated_delivery_date.isoformat() if o.estimated_delivery_date else None,
        "email": o.email,
        "customer_name": (o.address("shipping").full_name if o.address("shipping") else None),
        "thumbnails": [i.image_url for i in o.items[:4]],
        "first_item": o.items[0].product_name if o.items else None,
    }


def order_detail(o: Order, *, admin: bool = False) -> dict:
    d = order_summary(o)
    window_open = bool(o.delivered_at and utcnow() <= o.delivered_at + timedelta(days=7))
    d.update({
        "phone": o.phone,
        "currency": o.currency,
        "items": [
            {
                "id": i.id, "product_id": i.product_id, "variant_id": i.variant_id, "product_name": i.product_name,
                "product_slug": i.product_slug, "variant_name": i.variant_name, "sku": i.sku, "image_url": i.image_url,
                "attributes": i.attributes, "quantity": i.quantity, "returned_quantity": i.returned_quantity,
                "unit_mrp": M(i.unit_mrp), "unit_price": M(i.unit_price), "discount_amount": M(i.discount_amount),
                "tax_rate": M(i.tax_rate), "tax_amount": M(i.tax_amount), "line_total": M(i.line_total),
                **({"unit_cost": M(i.unit_cost)} if admin else {}),
            }
            for i in o.items
        ],
        "totals": {
            "subtotal_mrp": M(o.subtotal_mrp), "subtotal": M(o.subtotal), "item_discount": M(o.item_discount_total),
            "promotion_discount": M(o.promotion_discount), "coupon_discount": M(o.coupon_discount),
            "coupon_code": o.coupon_code, "shipping_charge": M(o.shipping_charge), "cod_charge": M(o.cod_charge),
            "tax_total": M(o.tax_total), "grand_total": M(o.grand_total), "refunded_total": M(o.refunded_total),
        },
        "applied_promotions": o.applied_promotions or [],
        "shipping_address": address_dict(o.address("shipping")),
        "billing_address": address_dict(o.address("billing")),
        "shipping_method_name": o.shipping_method_name,
        "estimated_dispatch_date": o.estimated_dispatch_date.isoformat() if o.estimated_dispatch_date else None,
        "customer_note": o.customer_note,
        "cancellation_reason": o.cancellation_reason,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
        "cancelled_at": o.cancelled_at.isoformat() if o.cancelled_at else None,
        "payments": [
            {
                "id": p.id, "provider": p.provider, "mode": p.mode, "method": p.method, "status": p.status,
                "amount": M(from_paise(p.amount_paise)), "amount_refunded": M(from_paise(p.amount_refunded_paise)),
                "razorpay_order_id": p.razorpay_order_id, "razorpay_payment_id": p.razorpay_payment_id,
                "error_description": p.error_description, "attempts": p.attempts,
                "created_at": p.created_at.isoformat(), "captured_at": p.captured_at.isoformat() if p.captured_at else None,
            }
            for p in o.payments
        ],
        "refunds": [
            {"id": r.id, "amount": M(from_paise(r.amount_paise)), "status": r.status, "reason": r.reason,
             "razorpay_refund_id": r.razorpay_refund_id, "created_at": r.created_at.isoformat(),
             "processed_at": r.processed_at.isoformat() if r.processed_at else None}
            for r in o.refunds
        ],
        "shipments": [
            {"id": s.id, "courier_name": s.courier_name, "tracking_number": s.tracking_number, "tracking_url": s.tracking_url,
             "status": s.status, "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
             "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
             "events": [{"status": e.status, "location": e.location, "description": e.description, "occurred_at": e.occurred_at.isoformat()}
                        for e in sorted(s.events, key=lambda e: e.occurred_at, reverse=True)]}
            for s in o.shipments
        ],
        "history": [
            {"from": h.from_status, "to": h.to_status, "label": STATUS_LABELS.get(h.to_status, h.to_status), "note": h.note,
             "actor_type": h.actor_type, "at": h.created_at.isoformat()}
            for h in o.history
        ],
        "timeline": _timeline(o),
        "can_cancel": o.status in CUSTOMER_CANCELLABLE,
        "can_request_cancel": o.status in CUSTOMER_CANCEL_REQUESTABLE,
        "can_return": o.status == "delivered" and window_open,
        "can_pay": o.status == "payment_pending" and o.payment_method == "razorpay" and o.payment_status != "paid",
        "can_review": o.status in ("delivered", "return_requested", "returned"),
        "invoice_available": o.payment_status in ("paid", "partially_refunded", "refunded") or o.payment_method == "cod",
    })
    if admin:
        d["allowed_transitions"] = [{"value": s, "label": STATUS_LABELS[s]} for s in allowed_next(o)]
        d["notes"] = [{"id": n.id, "author": n.author_name, "body": n.body, "at": n.created_at.isoformat()} for n in o.notes]
        d["user_id"] = o.user_id
        d["idempotency_key"] = o.idempotency_key
    return d


def _timeline(o: Order) -> list[dict]:
    reached = {h.to_status: h.created_at for h in o.history}
    if o.payment_method == "cod":
        steps = [s for s in CUSTOMER_TIMELINE if s != "payment_confirmed"]
    else:
        steps = ["payment_pending" if "payment_confirmed" not in reached else "order_placed"] + CUSTOMER_TIMELINE[1:]
        if "payment_confirmed" in reached:
            reached.setdefault("order_placed", o.placed_at)
    out = []
    for s in steps:
        out.append({"status": s, "label": STATUS_LABELS[s], "done": s in reached or (s == "order_placed"),
                    "at": reached[s].isoformat() if s in reached else (o.placed_at.isoformat() if s == "order_placed" else None)})
    terminal = [s for s in ("cancellation_requested", "cancelled", "delivery_failed", "return_requested", "returned", "refund_initiated", "refunded") if s in reached]
    for s in terminal:
        out.append({"status": s, "label": STATUS_LABELS[s], "done": True, "at": reached[s].isoformat(), "exception": True})
    return out
