"""Reporting. Metric definitions (also shown in the admin UI and docs/ARCHITECTURE.md (Reports)):

  Counted order   : online order with captured payment (paid_at set), or a COD order that was not
                    cancelled. Pending/abandoned payments never count.
  Gross sales     : Σ order.subtotal (selling price × qty, before order-level discounts).
  Discounts       : Σ (promotion_discount + coupon_discount). MRP markdowns are reported separately.
  Refunds         : Σ processed refunds created in the period.
  Net sales       : Gross sales − Discounts − Refunds.
  Revenue         : Σ grand_total (what customers were charged, incl. shipping & COD fees).
  AOV             : Revenue ÷ counted orders.
  GST collected   : Σ tax_total (included in prices).
  Gross margin    : Σ (line_total − unit_cost × qty) for lines with cost data — admins only.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.money import ZERO, from_paise, q
from app.models import (
    Category,
    Coupon,
    CouponRedemption,
    Inventory,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductVariant,
    Refund,
    ReturnRequest,
    User,
    user_roles,
    Role,
)

M = lambda v: f"{q(v or 0):.2f}"  # noqa: E731


def counted_clause():
    return or_(Order.paid_at.is_not(None), and_(Order.payment_method == "cod", Order.status != "cancelled"))


def date_range(start: date | None, end: date | None, default_days: int = 30) -> tuple[datetime, datetime]:
    end_d = end or utcnow().date()
    start_d = start or (end_d - timedelta(days=default_days - 1))
    return datetime.combine(start_d, datetime.min.time()), datetime.combine(end_d + timedelta(days=1), datetime.min.time())


def _period_expr(db: Session, granularity: str):
    dialect = db.bind.dialect.name
    col = Order.placed_at
    if dialect == "sqlite":
        fmt = {"day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m", "year": "%Y"}[granularity]
        return func.strftime(fmt, col)
    fmt = {"day": "%Y-%m-%d", "week": "%x-W%v", "month": "%Y-%m", "year": "%Y"}[granularity]
    return func.date_format(col, fmt)


def summary(db: Session, start: datetime, end: datetime, include_cost: bool) -> dict:
    base = and_(counted_clause(), Order.placed_at >= start, Order.placed_at < end)
    row = db.execute(
        select(
            func.count(Order.id), func.coalesce(func.sum(Order.subtotal), 0), func.coalesce(func.sum(Order.promotion_discount), 0),
            func.coalesce(func.sum(Order.coupon_discount), 0), func.coalesce(func.sum(Order.grand_total), 0),
            func.coalesce(func.sum(Order.tax_total), 0), func.coalesce(func.sum(Order.item_discount_total), 0),
            func.coalesce(func.sum(Order.shipping_charge), 0),
        ).where(base)
    ).one()
    count, gross, promo, coupon, revenue, tax, markdown, shipping = row
    refunds_paise = db.scalar(
        select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(Refund.status == "processed", Refund.created_at >= start, Refund.created_at < end)
    ) or 0
    refunds = from_paise(int(refunds_paise))
    discounts = q(promo) + q(coupon)
    out = {
        "orders": int(count),
        "gross_sales": M(gross),
        "discounts": M(discounts),
        "markdowns": M(markdown),
        "refunds": M(refunds),
        "net_sales": M(q(gross) - discounts - refunds),
        "revenue": M(revenue),
        "shipping_collected": M(shipping),
        "tax_collected": M(tax),
        "aov": M(q(revenue) / count if count else 0),
    }
    if include_cost:
        margin = db.scalar(
            select(func.coalesce(func.sum(OrderItem.line_total - OrderItem.unit_cost * OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id).where(base, OrderItem.unit_cost.is_not(None))
        )
        out["gross_margin"] = M(margin)
    return out


def dashboard(db: Session, start: datetime, end: datetime, include_cost: bool) -> dict:
    s = summary(db, start, end, include_cost)
    span = end - start
    prev = summary(db, start - span, start, False)
    customers = db.scalar(select(func.count(func.distinct(User.id))).join(user_roles, user_roles.c.user_id == User.id)
                          .join(Role, Role.id == user_roles.c.role_id).where(Role.name == "customer"))
    new_customers = db.scalar(select(func.count(func.distinct(User.id))).join(user_roles, user_roles.c.user_id == User.id)
                              .join(Role, Role.id == user_roles.c.role_id).where(Role.name == "customer", User.created_at >= start, User.created_at < end))
    products = db.scalar(select(func.count(Product.id)).where(Product.status == "active"))
    pending = db.scalar(select(func.count(Order.id)).where(Order.status.in_(["order_placed", "payment_confirmed"])))
    awaiting = db.scalar(select(func.count(Order.id)).where(Order.status.in_(["processing", "packed"])))
    cancel_req = db.scalar(select(func.count(Order.id)).where(Order.status == "cancellation_requested"))
    returns_open = db.scalar(select(func.count(ReturnRequest.id)).where(ReturnRequest.status.in_(["requested", "approved"])))
    low = low_stock(db, limit=8)
    recent = db.scalars(select(Order).order_by(Order.placed_at.desc()).limit(8)).all()
    from app.services.serializers import order_summary

    return {
        "range": {"start": start.date().isoformat(), "end": (end - timedelta(days=1)).date().isoformat()},
        "summary": s,
        "previous": prev,
        "totals": {"customers": customers, "new_customers": new_customers, "products": products},
        "queues": {"pending_orders": pending, "awaiting_dispatch": awaiting, "cancellation_requests": cancel_req, "open_returns": returns_open,
                   "low_stock": len(low_stock(db, limit=1000))},
        "sales_trend": sales_series(db, start, end, "day"),
        "sales_by_category": category_performance(db, start, end)[:8],
        "payment_methods": payment_breakdown(db, start, end),
        "best_sellers": product_performance(db, start, end, limit=6, include_cost=False),
        "low_stock": low,
        "recent_orders": [order_summary(o) for o in recent],
        "definitions": __doc__,
    }


def sales_series(db: Session, start: datetime, end: datetime, granularity: str = "day") -> list[dict]:
    period = _period_expr(db, granularity).label("period")
    rows = db.execute(
        select(period, func.count(Order.id), func.coalesce(func.sum(Order.subtotal - Order.promotion_discount - Order.coupon_discount), 0),
               func.coalesce(func.sum(Order.grand_total), 0))
        .where(counted_clause(), Order.placed_at >= start, Order.placed_at < end).group_by(period).order_by(period)
    ).all()
    by = {r[0]: r for r in rows}
    out = []
    if granularity == "day":
        d = start.date()
        while d < end.date():
            k = d.isoformat()
            r = by.get(k)
            out.append({"period": k, "orders": int(r[1]) if r else 0, "net_sales": M(r[2] if r else 0), "revenue": M(r[3] if r else 0)})
            d += timedelta(days=1)
        return out
    return [{"period": r[0], "orders": int(r[1]), "net_sales": M(r[2]), "revenue": M(r[3])} for r in rows]


def payment_breakdown(db: Session, start: datetime, end: datetime) -> list[dict]:
    method = case((Order.payment_method == "cod", "cod"), else_=func.coalesce(Payment.method, "online"))
    rows = db.execute(
        select(method.label("m"), func.count(func.distinct(Order.id)), func.coalesce(func.sum(Order.grand_total), 0))
        .select_from(Order)
        .outerjoin(Payment, and_(Payment.order_id == Order.id, Payment.status.in_(["captured", "refunded", "partially_refunded", "cod_pending", "cod_collected"])))
        .where(counted_clause(), Order.placed_at >= start, Order.placed_at < end).group_by("m")
    ).all()
    labels = {"upi": "UPI", "card": "Cards", "netbanking": "Net Banking", "wallet": "Wallets", "cod": "Cash on Delivery", "online": "Online"}
    return [{"method": labels.get(m, m), "orders": int(c), "amount": M(a)} for m, c, a in rows]


def product_performance(db: Session, start: datetime, end: datetime, limit: int = 50, include_cost: bool = False) -> list[dict]:
    cols = [OrderItem.product_id, func.max(OrderItem.product_name), func.max(OrderItem.sku), func.sum(OrderItem.quantity),
            func.coalesce(func.sum(OrderItem.line_total), 0), func.coalesce(func.sum(OrderItem.returned_quantity), 0)]
    if include_cost:
        cols.append(func.coalesce(func.sum(OrderItem.line_total - func.coalesce(OrderItem.unit_cost, 0) * OrderItem.quantity), 0))
    rows = db.execute(
        select(*cols).join(Order, Order.id == OrderItem.order_id)
        .where(counted_clause(), Order.placed_at >= start, Order.placed_at < end)
        .group_by(OrderItem.product_id).order_by(func.sum(OrderItem.quantity).desc()).limit(limit)
    ).all()
    out = []
    for r in rows:
        p = db.get(Product, r[0]) if r[0] else None
        d = {"product_id": r[0], "name": r[1], "sku": p.sku if p else r[2], "units": int(r[3]), "net_sales": M(r[4]), "returned_units": int(r[5]),
             "image": next((i.url for i in p.images), None) if p else None, "slug": p.slug if p else None}
        if include_cost:
            d["gross_margin"] = M(r[6])
        out.append(d)
    return out


def category_performance(db: Session, start: datetime, end: datetime) -> list[dict]:
    rows = db.execute(
        select(OrderItem.category_name, func.count(func.distinct(OrderItem.order_id)), func.sum(OrderItem.quantity), func.coalesce(func.sum(OrderItem.line_total), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(counted_clause(), Order.placed_at >= start, Order.placed_at < end)
        .group_by(OrderItem.category_name).order_by(func.sum(OrderItem.line_total).desc())
    ).all()
    return [{"category": r[0] or "Uncategorised", "orders": int(r[1]), "units": int(r[2]), "net_sales": M(r[3])} for r in rows]


def order_status_report(db: Session, start: datetime, end: datetime) -> list[dict]:
    from app.services.order_service import STATUS_LABELS

    rows = db.execute(select(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.grand_total), 0))
                      .where(Order.placed_at >= start, Order.placed_at < end).group_by(Order.status)).all()
    return [{"status": s, "label": STATUS_LABELS.get(s, s), "orders": int(c), "value": M(v)} for s, c, v in sorted(rows, key=lambda r: -r[1])]


def low_stock(db: Session, limit: int = 50) -> list[dict]:
    rows = db.execute(
        select(ProductVariant, Inventory).join(Inventory, Inventory.variant_id == ProductVariant.id).join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.is_active.is_(True), Product.status == "active",
               Inventory.quantity_on_hand - Inventory.quantity_reserved <= Inventory.low_stock_threshold)
        .order_by((Inventory.quantity_on_hand - Inventory.quantity_reserved).asc()).limit(limit)
    ).all()
    return [{"variant_id": v.id, "product_id": v.product_id, "product_name": v.product.name, "variant_name": v.name, "sku": v.sku,
             "on_hand": inv.quantity_on_hand, "reserved": inv.quantity_reserved, "available": inv.available,
             "threshold": inv.low_stock_threshold, "status": "out_of_stock" if inv.available <= 0 else "low_stock"} for v, inv in rows]


def inventory_report(db: Session, include_cost: bool) -> dict:
    rows = db.execute(select(ProductVariant, Inventory).join(Inventory, Inventory.variant_id == ProductVariant.id)
                      .where(ProductVariant.is_active.is_(True))).all()
    units = sum(inv.quantity_on_hand for _, inv in rows)
    retail = sum((q(v.sale_price) * inv.quantity_on_hand for v, inv in rows), ZERO)
    out = {"variants": len(rows), "units_on_hand": units, "units_reserved": sum(inv.quantity_reserved for _, inv in rows),
           "retail_value": M(retail), "out_of_stock": sum(1 for _, inv in rows if inv.available <= 0),
           "low_stock": sum(1 for _, inv in rows if 0 < inv.available <= inv.low_stock_threshold), "items": low_stock(db, 200)}
    if include_cost:
        out["cost_value"] = M(sum((q(v.cost_price or 0) * inv.quantity_on_hand for v, inv in rows), ZERO))
    return out


def coupon_performance(db: Session, start: datetime, end: datetime) -> list[dict]:
    rows = db.execute(
        select(Coupon.code, Coupon.discount_type, Coupon.value, Coupon.times_used, Coupon.usage_limit_total,
               func.count(CouponRedemption.id), func.coalesce(func.sum(CouponRedemption.discount_amount), 0),
               func.coalesce(func.sum(Order.grand_total), 0))
        .select_from(Coupon)
        .outerjoin(CouponRedemption, and_(CouponRedemption.coupon_id == Coupon.id, CouponRedemption.status == "applied",
                                          CouponRedemption.created_at >= start, CouponRedemption.created_at < end))
        .outerjoin(Order, Order.id == CouponRedemption.order_id)
        .group_by(Coupon.id, Coupon.code, Coupon.discount_type, Coupon.value, Coupon.times_used, Coupon.usage_limit_total)
        .order_by(func.count(CouponRedemption.id).desc())
    ).all()
    return [{"code": r[0], "type": r[1], "value": M(r[2]), "times_used_all_time": r[3], "usage_limit": r[4], "redemptions": int(r[5]),
             "discount_given": M(r[6]), "order_value": M(r[7])} for r in rows]


def customer_report(db: Session, start: datetime, end: datetime) -> dict:
    month = (func.strftime("%Y-%m", User.created_at) if db.bind.dialect.name == "sqlite" else func.date_format(User.created_at, "%Y-%m")).label("m")
    acq = db.execute(select(month, func.count(User.id)).join(user_roles, user_roles.c.user_id == User.id).join(Role, Role.id == user_roles.c.role_id)
                     .where(Role.name == "customer", User.created_at >= start, User.created_at < end).group_by(month).order_by(month)).all()
    per_customer = db.execute(select(Order.email, func.count(Order.id), func.sum(Order.grand_total)).where(counted_clause())
                              .group_by(Order.email)).all()
    buyers = len(per_customer)
    repeat = sum(1 for r in per_customer if r[1] > 1)
    top = sorted(per_customer, key=lambda r: r[2] or 0, reverse=True)[:10]
    return {
        "acquisition": [{"month": m, "new_customers": int(c)} for m, c in acq],
        "buyers": buyers, "repeat_buyers": repeat,
        "repeat_rate": round(repeat / buyers * 100, 1) if buyers else 0,
        "top_customers": [{"email": e, "orders": int(c), "lifetime_value": M(v)} for e, c, v in top],
    }


def refunds_report(db: Session, start: datetime, end: datetime) -> dict:
    cancelled = db.execute(select(func.count(Order.id), func.coalesce(func.sum(Order.grand_total), 0))
                           .where(Order.status.in_(["cancelled", "refund_initiated", "refunded"]), Order.cancelled_at >= start, Order.cancelled_at < end)).one()
    reasons = db.execute(select(Order.cancellation_reason, func.count(Order.id)).where(Order.cancelled_at >= start, Order.cancelled_at < end)
                         .group_by(Order.cancellation_reason).order_by(func.count(Order.id).desc()).limit(10)).all()
    ret = db.execute(select(ReturnRequest.reason, ReturnRequest.status, func.count(ReturnRequest.id))
                     .where(ReturnRequest.created_at >= start, ReturnRequest.created_at < end).group_by(ReturnRequest.reason, ReturnRequest.status)).all()
    refunds = db.execute(select(Refund.status, func.count(Refund.id), func.coalesce(func.sum(Refund.amount_paise), 0))
                         .where(Refund.created_at >= start, Refund.created_at < end).group_by(Refund.status)).all()
    return {
        "cancelled_orders": int(cancelled[0]), "cancelled_value": M(cancelled[1]),
        "cancellation_reasons": [{"reason": r or "Not specified", "count": int(c)} for r, c in reasons],
        "returns": [{"reason": r, "status": s, "count": int(c)} for r, s, c in ret],
        "refunds": [{"status": s, "count": int(c), "amount": M(from_paise(int(a)))} for s, c, a in refunds],
    }


def to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: (v if not isinstance(v, (list, dict)) else str(v)) for k, v in r.items()})
    return buf.getvalue()
