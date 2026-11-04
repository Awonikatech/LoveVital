"""Admin: inventory, customers, coupons, promotions, shipping, content, reports, audit log."""
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import request_ip, require_permission
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import (
    Address,
    AuditLog,
    Banner,
    CmsPage,
    Coupon,
    CouponRedemption,
    Inventory,
    InventoryMovement,
    InventoryReservation,
    NewsletterSubscriber,
    Order,
    Product,
    ProductVariant,
    Promotion,
    Role,
    ServiceablePinCode,
    ShippingMethod,
    StoreSetting,
    User,
    user_roles,
)
from app.services import catalog_service, inventory_service, report_service
from app.services.common import DEFAULT_SETTINGS, audit, get_setting, set_setting, slugify
from app.services.serializers import order_summary

router = APIRouter(tags=["admin: management"])


def _page(total: int, page: int, size: int) -> dict:
    return {"total": total, "page": page, "page_size": size, "pages": math.ceil(total / size) if total else 0}


# ================================================================== dashboard & reports
@router.get("/dashboard")
def dashboard(user: User = Depends(require_permission("dashboard:view")), db: Session = Depends(get_db),
              start: date | None = None, end: date | None = None):
    s, e = report_service.date_range(start, end)
    data = report_service.dashboard(db, s, e, include_cost=user.has_permission("products:cost"))
    if not user.has_permission("reports:view"):
        # Staff see operations, not finance.
        for k in ("gross_sales", "discounts", "markdowns", "refunds", "net_sales", "revenue", "tax_collected", "aov", "shipping_collected", "gross_margin"):
            data["summary"].pop(k, None)
            data["previous"].pop(k, None)
        data["sales_trend"] = [{"period": r["period"], "orders": r["orders"]} for r in data["sales_trend"]]
        data["sales_by_category"] = [{"category": r["category"], "units": r["units"], "orders": r["orders"]} for r in data["sales_by_category"]]
        data["payment_methods"] = [{"method": r["method"], "orders": r["orders"]} for r in data["payment_methods"]]
        data["finance_visible"] = False
    else:
        data["finance_visible"] = True
    return data


REPORTS = ["sales", "order_status", "products", "categories", "inventory", "coupons", "customers", "refunds"]


@router.get("/reports/{name}")
def report(name: Literal["sales", "order_status", "products", "categories", "inventory", "coupons", "customers", "refunds"],
           user: User = Depends(require_permission("reports:view")), db: Session = Depends(get_db),
           start: date | None = None, end: date | None = None, granularity: Literal["day", "week", "month", "year"] = "day",
           format: Literal["json", "csv"] = "json"):
    s, e = report_service.date_range(start, end, 365 if granularity in ("month", "year") else 30)
    cost = user.has_permission("products:cost")
    if name == "sales":
        data: Any = {"summary": report_service.summary(db, s, e, cost), "series": report_service.sales_series(db, s, e, granularity)}
        rows = data["series"]
    elif name == "order_status":
        data = rows = report_service.order_status_report(db, s, e)
    elif name == "products":
        data = rows = report_service.product_performance(db, s, e, 100, cost)
    elif name == "categories":
        data = rows = report_service.category_performance(db, s, e)
    elif name == "inventory":
        data = report_service.inventory_report(db, cost)
        rows = data["items"]
    elif name == "coupons":
        data = rows = report_service.coupon_performance(db, s, e)
    elif name == "customers":
        data = report_service.customer_report(db, s, e)
        rows = data["top_customers"]
    else:
        data = report_service.refunds_report(db, s, e)
        rows = data["refunds"] + data["returns"]
    if format == "csv":
        return PlainTextResponse(report_service.to_csv(rows), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{name}-report-{s:%Y%m%d}-{e:%Y%m%d}.csv"'})
    return {"report": name, "range": {"start": s.date().isoformat(), "end": e.date().isoformat()}, "data": data,
            "definitions": report_service.__doc__}


# ================================================================== inventory
@router.get("/inventory")
def list_inventory(user: User = Depends(require_permission("inventory:read")), db: Session = Depends(get_db), q: str | None = None,
                   stock: Literal["low", "out", "in"] | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, le=100)):
    avail = Inventory.quantity_on_hand - Inventory.quantity_reserved
    stmt = select(ProductVariant, Inventory).join(Inventory, Inventory.variant_id == ProductVariant.id).join(Product, Product.id == ProductVariant.product_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(ProductVariant.sku).like(like), func.lower(Product.name).like(like)))
    if stock == "out":
        stmt = stmt.where(avail <= 0)
    elif stock == "low":
        stmt = stmt.where(avail > 0, avail <= Inventory.low_stock_threshold)
    elif stock == "in":
        stmt = stmt.where(avail > Inventory.low_stock_threshold)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(avail.asc(), ProductVariant.sku).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"variant_id": v.id, "product_id": v.product_id, "product_name": v.product.name, "variant_name": v.name, "sku": v.sku,
                       "image": next((i.url for i in v.product.images), None), "on_hand": inv.quantity_on_hand, "reserved": inv.quantity_reserved,
                       "available": inv.available, "low_stock_threshold": inv.low_stock_threshold, "is_active": v.is_active,
                       "status": "out_of_stock" if inv.available <= 0 else ("low_stock" if inv.available <= inv.low_stock_threshold else "in_stock")}
                      for v, inv in rows], **_page(total, page, page_size)}


class AdjustIn(BaseModel):
    variant_id: int
    delta: int = Field(ge=-100000, le=100000)
    movement_type: Literal["restock", "adjustment", "damage", "return"] = "adjustment"
    note: str | None = Field(default=None, max_length=255)
    low_stock_threshold: int | None = Field(default=None, ge=0)


@router.post("/inventory/adjust")
def adjust(body: AdjustIn, request: Request, user: User = Depends(require_permission("inventory:write")), db: Session = Depends(get_db)):
    if body.delta == 0 and body.low_stock_threshold is None:
        raise ValidationFailed("Nothing to change")
    inv = inventory_service.adjust(db, body.variant_id, body.delta, body.movement_type, body.note, user, body.low_stock_threshold)
    audit(db, user, "inventory.adjust", "variant", body.variant_id, body.model_dump(), request_ip(request))
    db.commit()
    return {"variant_id": inv.variant_id, "on_hand": inv.quantity_on_hand, "reserved": inv.quantity_reserved, "available": inv.available,
            "low_stock_threshold": inv.low_stock_threshold}


@router.get("/inventory/movements")
def movements(user: User = Depends(require_permission("inventory:read")), db: Session = Depends(get_db), variant_id: int | None = None,
              movement_type: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(30, le=200)):
    stmt = select(InventoryMovement)
    if variant_id:
        stmt = stmt.where(InventoryMovement.variant_id == variant_id)
    if movement_type:
        stmt = stmt.where(InventoryMovement.movement_type == movement_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(InventoryMovement.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    users = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({m.created_by_id for m in rows if m.created_by_id}))).all()}
    return {"items": [{"id": m.id, "sku": m.variant.sku, "product_name": m.variant.product.name, "variant_name": m.variant.name,
                       "movement_type": m.movement_type, "quantity": m.quantity, "balance_after": m.balance_after, "reference": m.reference_id,
                       "note": m.note, "by": users.get(m.created_by_id, "System"), "at": m.created_at.isoformat()} for m in rows],
            **_page(total, page, page_size)}


@router.get("/inventory/reservations")
def reservations(user: User = Depends(require_permission("inventory:read")), db: Session = Depends(get_db), status: str = "active"):
    rows = db.scalars(select(InventoryReservation).where(InventoryReservation.status == status).order_by(InventoryReservation.expires_at).limit(200)).all()
    out = []
    for r in rows:
        v = db.get(ProductVariant, r.variant_id)
        o = db.get(Order, r.order_id)
        out.append({"id": r.id, "sku": v.sku if v else None, "order_number": o.order_number if o else None, "order_id": r.order_id,
                    "quantity": r.quantity, "status": r.status, "expires_at": r.expires_at.isoformat(), "release_reason": r.release_reason})
    return out


@router.post("/inventory/sweep-reservations")
def sweep(user: User = Depends(require_permission("inventory:write")), db: Session = Depends(get_db)):
    return {"released_orders": inventory_service.sweep_expired(db)}


# ================================================================== customers
def _customers_stmt():
    return select(User).join(user_roles, user_roles.c.user_id == User.id).join(Role, Role.id == user_roles.c.role_id).where(Role.name == "customer")


@router.get("/customers")
def list_customers(user: User = Depends(require_permission("customers:read")), db: Session = Depends(get_db), q: str | None = None,
                   status: Literal["active", "disabled"] | None = None, sort: Literal["newest", "spend", "orders", "name"] = "newest",
                   page: int = Query(1, ge=1), page_size: int = Query(20, le=100)):
    stats = (select(Order.user_id.label("uid"), func.count(Order.id).label("orders"), func.coalesce(func.sum(Order.grand_total), 0).label("spend"),
                    func.max(Order.placed_at).label("last"))
             .where(report_service.counted_clause()).group_by(Order.user_id).subquery())
    stmt = select(User, stats.c.orders, stats.c.spend, stats.c.last).join(user_roles, user_roles.c.user_id == User.id) \
        .join(Role, Role.id == user_roles.c.role_id).outerjoin(stats, stats.c.uid == User.id).where(Role.name == "customer")
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like), User.phone.like(like)))
    if status:
        stmt = stmt.where(User.is_active.is_(status == "active"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = {"newest": User.id.desc(), "spend": func.coalesce(stats.c.spend, 0).desc(), "orders": func.coalesce(stats.c.orders, 0).desc(),
             "name": User.full_name.asc()}[sort]
    rows = db.execute(stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "is_active": u.is_active,
                       "email_verified": bool(u.email_verified_at), "created_at": u.created_at.isoformat(), "orders": int(o or 0),
                       "total_spend": f"{(s or 0):.2f}", "last_order_at": last.isoformat() if last else None} for u, o, s, last in rows],
            **_page(total, page, page_size)}


@router.get("/customers/{uid}")
def get_customer(uid: int, user: User = Depends(require_permission("customers:read")), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise NotFound("Customer not found")
    orders = db.scalars(select(Order).where(or_(Order.user_id == u.id, Order.email == u.email)).order_by(Order.placed_at.desc())).all()
    counted = [o for o in orders if o.paid_at or (o.payment_method == "cod" and o.status != "cancelled")]
    return {
        "id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "is_active": u.is_active, "disabled_reason": u.disabled_reason,
        "email_verified_at": u.email_verified_at.isoformat() if u.email_verified_at else None, "created_at": u.created_at.isoformat(),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None, "support_notes": u.support_notes, "roles": u.role_names,
        "addresses": [{"id": a.id, "label": a.label, "full_name": a.full_name, "phone": a.phone, "line1": a.line1, "line2": a.line2,
                       "city": a.city, "state": a.state, "pin_code": a.pin_code, "is_default_shipping": a.is_default_shipping} for a in u.addresses],
        "orders": [order_summary(o) for o in orders],
        "stats": {"orders": len(counted), "lifetime_value": f"{sum((o.grand_total for o in counted), Decimal(0)):.2f}",
                  "aov": f"{(sum((o.grand_total for o in counted), Decimal(0)) / len(counted)) if counted else 0:.2f}",
                  "refunded": f"{sum((o.refunded_total for o in orders), Decimal(0)):.2f}"},
    }


class CustomerPatch(BaseModel):
    is_active: bool | None = None
    disabled_reason: str | None = Field(default=None, max_length=255)
    support_notes: str | None = Field(default=None, max_length=5000)


@router.patch("/customers/{uid}")
def patch_customer(uid: int, body: CustomerPatch, request: Request, user: User = Depends(require_permission("customers:read")), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise NotFound("Customer not found")
    if body.is_active is not None:
        if not user.has_permission("customers:write"):
            raise ValidationFailed("Only administrators can disable or enable accounts", code="forbidden")
        if u.id == user.id:
            raise ValidationFailed("You cannot disable your own account")
        if body.is_active is False and not body.disabled_reason:
            raise ValidationFailed("Give a reason for disabling this account (required by policy)")
        u.is_active = body.is_active
        u.disabled_reason = None if body.is_active else body.disabled_reason
        if not body.is_active:
            from sqlalchemy import update

            from app.core.database import utcnow
            from app.models import RefreshToken

            db.execute(update(RefreshToken).where(RefreshToken.user_id == u.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow()))
    if body.support_notes is not None:
        u.support_notes = body.support_notes
    audit(db, user, "customer.update", "user", u.id, body.model_dump(exclude_none=True), request_ip(request))
    db.commit()
    return {"ok": True, "is_active": u.is_active}


# ================================================================== coupons & promotions
class CouponIn(BaseModel):
    code: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    description: str | None = Field(default=None, max_length=255)
    discount_type: Literal["percent", "fixed", "free_shipping"]
    value: Decimal = Field(default=Decimal(0), ge=0)
    min_cart_value: Decimal = Field(default=Decimal(0), ge=0)
    max_discount: Decimal | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    usage_limit_total: int | None = Field(default=None, ge=1)
    usage_limit_per_user: int | None = Field(default=1, ge=1)
    first_order_only: bool = False
    applies_to: Literal["all", "categories", "products"] = "all"
    category_ids: list[int] = []
    product_ids: list[int] = []
    customer_emails: list[EmailStr] = []
    combinable_with_promotions: bool = True
    is_active: bool = True

    @model_validator(mode="after")
    def _check(self):
        if self.discount_type == "percent" and not (0 < self.value <= 90):
            raise ValueError("Percentage must be between 1 and 90")
        if self.discount_type == "fixed" and self.value <= 0:
            raise ValueError("Fixed discount must be greater than 0")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("End date must be after start date")
        if self.applies_to == "categories" and not self.category_ids:
            raise ValueError("Choose at least one category")
        if self.applies_to == "products" and not self.product_ids:
            raise ValueError("Choose at least one product")
        return self


def _coupon(c: Coupon) -> dict:
    return {"id": c.id, "code": c.code, "description": c.description, "discount_type": c.discount_type, "value": f"{c.value:.2f}",
            "min_cart_value": f"{c.min_cart_value:.2f}", "max_discount": f"{c.max_discount:.2f}" if c.max_discount is not None else None,
            "starts_at": c.starts_at.isoformat() if c.starts_at else None, "ends_at": c.ends_at.isoformat() if c.ends_at else None,
            "usage_limit_total": c.usage_limit_total, "usage_limit_per_user": c.usage_limit_per_user, "times_used": c.times_used,
            "first_order_only": c.first_order_only, "applies_to": c.applies_to, "category_ids": c.category_ids or [], "product_ids": c.product_ids or [],
            "customer_emails": c.customer_emails or [], "combinable_with_promotions": c.combinable_with_promotions, "is_active": c.is_active}


@router.get("/coupons")
def list_coupons(user: User = Depends(require_permission("coupons:read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Coupon).order_by(Coupon.id.desc())).all()
    disc = dict(db.execute(select(CouponRedemption.coupon_id, func.sum(CouponRedemption.discount_amount)).where(CouponRedemption.status == "applied")
                           .group_by(CouponRedemption.coupon_id)).all())
    return [_coupon(c) | {"discount_given": f"{disc.get(c.id, 0) or 0:.2f}"} for c in rows]


def _save_coupon(db: Session, c: Coupon, body: CouponIn) -> None:
    code = body.code.upper()
    if db.scalar(select(Coupon.id).where(func.upper(Coupon.code) == code, Coupon.id != (c.id or 0))):
        raise Conflict(f"Coupon code {code} already exists", code="duplicate_code")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    c.code = code
    c.customer_emails = [str(e).lower() for e in body.customer_emails] or None


@router.post("/coupons", status_code=201)
def create_coupon(body: CouponIn, request: Request, user: User = Depends(require_permission("coupons:write")), db: Session = Depends(get_db)):
    c = Coupon(code=body.code.upper(), discount_type=body.discount_type)
    _save_coupon(db, c, body)
    db.add(c)
    db.flush()
    audit(db, user, "coupon.create", "coupon", c.id, body.model_dump(), request_ip(request))
    db.commit()
    return _coupon(c)


@router.put("/coupons/{cid}")
def update_coupon(cid: int, body: CouponIn, request: Request, user: User = Depends(require_permission("coupons:write")), db: Session = Depends(get_db)):
    c = db.get(Coupon, cid)
    if not c:
        raise NotFound("Coupon not found")
    _save_coupon(db, c, body)
    audit(db, user, "coupon.update", "coupon", c.id, body.model_dump(), request_ip(request))
    db.commit()
    return _coupon(c)


@router.delete("/coupons/{cid}")
def delete_coupon(cid: int, request: Request, user: User = Depends(require_permission("coupons:write")), db: Session = Depends(get_db)):
    c = db.get(Coupon, cid)
    if not c:
        raise NotFound("Coupon not found")
    if db.scalar(select(CouponRedemption.id).where(CouponRedemption.coupon_id == cid).limit(1)):
        c.is_active = False
        msg = "Coupon has been used, so it was deactivated instead of deleted."
    else:
        db.delete(c)
        msg = "Coupon deleted."
    audit(db, user, "coupon.delete", "coupon", cid, None, request_ip(request))
    db.commit()
    return {"message": msg}


@router.get("/coupons/{cid}/redemptions")
def coupon_redemptions(cid: int, user: User = Depends(require_permission("coupons:read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(CouponRedemption).where(CouponRedemption.coupon_id == cid).order_by(CouponRedemption.id.desc()).limit(500)).all()
    return [{"id": r.id, "order_id": r.order_id, "order_number": db.get(Order, r.order_id).order_number, "email": r.email,
             "discount_amount": f"{r.discount_amount:.2f}", "status": r.status, "at": r.created_at.isoformat()} for r in rows]


class PromotionIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    badge_text: str | None = Field(default=None, max_length=40)
    promo_type: Literal["percent_off", "fixed_off", "bogo", "quantity_discount", "free_shipping"]
    value: Decimal = Field(default=Decimal(0), ge=0)
    config: dict[str, Any] = {}
    applies_to: Literal["all", "categories", "products"] = "all"
    category_ids: list[int] = []
    product_ids: list[int] = []
    priority: int = Field(default=100, ge=0, le=10000)
    is_stackable: bool = True
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.promo_type in ("percent_off", "quantity_discount") and not (0 < self.value <= 90):
            raise ValueError("Percentage must be between 1 and 90")
        if self.promo_type == "bogo":
            b, g = int(self.config.get("buy_qty", 1)), int(self.config.get("get_qty", 1))
            if b < 1 or g < 1:
                raise ValueError("BOGO needs buy_qty ≥ 1 and get_qty ≥ 1")
        if self.promo_type == "quantity_discount" and int(self.config.get("min_qty", 0)) < 2:
            raise ValueError("Quantity discount needs config.min_qty ≥ 2")
        return self


def _promo(p: Promotion) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description, "badge_text": p.badge_text, "promo_type": p.promo_type,
            "value": f"{p.value:.2f}", "config": p.config or {}, "applies_to": p.applies_to, "category_ids": p.category_ids or [],
            "product_ids": p.product_ids or [], "priority": p.priority, "is_stackable": p.is_stackable, "is_active": p.is_active,
            "starts_at": p.starts_at.isoformat() if p.starts_at else None, "ends_at": p.ends_at.isoformat() if p.ends_at else None}


@router.get("/promotions")
def list_promotions(user: User = Depends(require_permission("coupons:read")), db: Session = Depends(get_db)):
    return [_promo(p) for p in db.scalars(select(Promotion).order_by(Promotion.priority, Promotion.id)).all()]


@router.post("/promotions", status_code=201)
def create_promotion(body: PromotionIn, request: Request, user: User = Depends(require_permission("coupons:write")), db: Session = Depends(get_db)):
    if db.scalar(select(Promotion.id).where(Promotion.name == body.name)):
        raise Conflict("A promotion with that name exists")
    p = Promotion(**body.model_dump())
    db.add(p)
    db.flush()
    audit(db, user, "promotion.create", "promotion", p.id, body.model_dump(), request_ip(request))
    db.commit()
    return _promo(p)


@router.put("/promotions/{pid}")
def update_promotion(pid: int, body: PromotionIn, request: Request, user: User = Depends(require_permission("coupons:write")), db: Session = Depends(get_db)):
    p = db.get(Promotion, pid)
    if not p:
        raise NotFound("Promotion not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    audit(db, user, "promotion.update", "promotion", p.id, body.model_dump(), request_ip(request))
    db.commit()
    return _promo(p)


@router.delete("/promotions/{pid}")
def delete_promotion(pid: int, request: Request, user: User = Depends(require_permission("coupons:write")), db: Session = Depends(get_db)):
    p = db.get(Promotion, pid)
    if not p:
        raise NotFound("Promotion not found")
    db.delete(p)
    audit(db, user, "promotion.delete", "promotion", pid, None, request_ip(request))
    db.commit()
    return {"deleted": True}


# ================================================================== shipping
class ShippingMethodIn(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=2, max_length=80)
    description: str | None = None
    carrier: str = "LoveVital Logistics (Mock)"
    base_charge: Decimal = Field(ge=0)
    free_shipping_threshold: Decimal | None = Field(default=None, ge=0)
    min_days: int = Field(ge=0, le=60)
    max_days: int = Field(ge=0, le=60)
    is_cod_allowed: bool = True
    is_active: bool = True
    display_order: int = 0

    @model_validator(mode="after")
    def _days(self):
        if self.max_days < self.min_days:
            raise ValueError("max_days must be ≥ min_days")
        return self


def _sm(m: ShippingMethod) -> dict:
    return {"id": m.id, "code": m.code, "name": m.name, "description": m.description, "carrier": m.carrier, "base_charge": f"{m.base_charge:.2f}",
            "free_shipping_threshold": f"{m.free_shipping_threshold:.2f}" if m.free_shipping_threshold is not None else None,
            "min_days": m.min_days, "max_days": m.max_days, "is_cod_allowed": m.is_cod_allowed, "is_active": m.is_active, "display_order": m.display_order}


@router.get("/shipping/methods")
def list_methods(user: User = Depends(require_permission("shipping:read")), db: Session = Depends(get_db)):
    return [_sm(m) for m in db.scalars(select(ShippingMethod).order_by(ShippingMethod.display_order)).all()]


@router.post("/shipping/methods", status_code=201)
def create_method(body: ShippingMethodIn, request: Request, user: User = Depends(require_permission("shipping:write")), db: Session = Depends(get_db)):
    if db.scalar(select(ShippingMethod.id).where(ShippingMethod.code == body.code)):
        raise Conflict("Code already exists")
    m = ShippingMethod(**body.model_dump())
    db.add(m)
    db.flush()
    audit(db, user, "shipping_method.create", "shipping_method", m.id, body.model_dump(), request_ip(request))
    db.commit()
    return _sm(m)


@router.put("/shipping/methods/{mid}")
def update_method(mid: int, body: ShippingMethodIn, request: Request, user: User = Depends(require_permission("shipping:write")), db: Session = Depends(get_db)):
    m = db.get(ShippingMethod, mid)
    if not m:
        raise NotFound("Shipping method not found")
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    audit(db, user, "shipping_method.update", "shipping_method", m.id, body.model_dump(), request_ip(request))
    db.commit()
    return _sm(m)


class PinIn(BaseModel):
    pin_code: str = Field(pattern=r"^([1-9][0-9]{5}|[1-9][0-9]{2})$", description="6-digit PIN or 3-digit prefix")
    city: str | None = None
    state: str | None = None
    region: Literal["metro", "regional", "national", "remote"] = "national"
    extra_days: int = Field(default=0, ge=0, le=30)
    is_serviceable: bool = True
    is_cod_available: bool = True


def _pin(p: ServiceablePinCode) -> dict:
    return {"id": p.id, "pin_code": p.pin_code, "city": p.city, "state": p.state, "region": p.region, "extra_days": p.extra_days,
            "is_serviceable": p.is_serviceable, "is_cod_available": p.is_cod_available}


@router.get("/shipping/pincodes")
def list_pins(user: User = Depends(require_permission("shipping:read")), db: Session = Depends(get_db), q: str | None = None,
              page: int = Query(1, ge=1), page_size: int = Query(50, le=200)):
    stmt = select(ServiceablePinCode)
    if q:
        stmt = stmt.where(or_(ServiceablePinCode.pin_code.like(f"{q}%"), func.lower(ServiceablePinCode.city).like(f"%{q.lower()}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(ServiceablePinCode.pin_code).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_pin(p) for p in rows], **_page(total, page, page_size)}


@router.post("/shipping/pincodes", status_code=201)
def upsert_pin(body: PinIn, request: Request, user: User = Depends(require_permission("shipping:write")), db: Session = Depends(get_db)):
    p = db.scalar(select(ServiceablePinCode).where(ServiceablePinCode.pin_code == body.pin_code))
    if not p:
        p = ServiceablePinCode(pin_code=body.pin_code)
        db.add(p)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.flush()
    audit(db, user, "pincode.upsert", "pincode", p.pin_code, body.model_dump(), request_ip(request))
    db.commit()
    return _pin(p)


@router.delete("/shipping/pincodes/{pid}")
def delete_pin(pid: int, user: User = Depends(require_permission("shipping:write")), db: Session = Depends(get_db)):
    p = db.get(ServiceablePinCode, pid)
    if not p:
        raise NotFound("PIN rule not found")
    db.delete(p)
    db.commit()
    return {"deleted": True}


# ================================================================== content
class BannerIn(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    subtitle: str | None = Field(default=None, max_length=300)
    eyebrow: str | None = Field(default=None, max_length=80)
    image_url: str = Field(max_length=500)
    cta_text: str | None = Field(default=None, max_length=50)
    cta_link: str | None = Field(default=None, max_length=300)
    placement: Literal["hero", "promo", "strip"] = "hero"
    display_order: int = 0
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("cta_link")
    @classmethod
    def _link(cls, v):
        if v and not (v.startswith("/") or v.startswith("https://")):
            raise ValueError("Link must be a site path (/...) or https URL")
        return v


def _banner(b: Banner) -> dict:
    return {"id": b.id, "title": b.title, "subtitle": b.subtitle, "eyebrow": b.eyebrow, "image_url": b.image_url, "cta_text": b.cta_text,
            "cta_link": b.cta_link, "placement": b.placement, "display_order": b.display_order, "is_active": b.is_active,
            "starts_at": b.starts_at.isoformat() if b.starts_at else None, "ends_at": b.ends_at.isoformat() if b.ends_at else None}


@router.get("/banners")
def list_banners(user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db)):
    return [_banner(b) for b in db.scalars(select(Banner).order_by(Banner.placement, Banner.display_order)).all()]


@router.post("/banners", status_code=201)
def create_banner(body: BannerIn, request: Request, user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db)):
    b = Banner(**body.model_dump())
    db.add(b)
    db.flush()
    audit(db, user, "banner.create", "banner", b.id, {"title": b.title}, request_ip(request))
    db.commit()
    return _banner(b)


@router.put("/banners/{bid}")
def update_banner(bid: int, body: BannerIn, request: Request, user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db)):
    b = db.get(Banner, bid)
    if not b:
        raise NotFound("Banner not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    audit(db, user, "banner.update", "banner", b.id, {"title": b.title}, request_ip(request))
    db.commit()
    return _banner(b)


@router.delete("/banners/{bid}")
def delete_banner(bid: int, request: Request, user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db)):
    b = db.get(Banner, bid)
    if not b:
        raise NotFound("Banner not found")
    db.delete(b)
    audit(db, user, "banner.delete", "banner", bid, None, request_ip(request))
    db.commit()
    return {"deleted": True}


class PageIn(BaseModel):
    slug: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1)
    seo_title: str | None = None
    seo_description: str | None = None
    is_published: bool = True


@router.get("/pages")
def list_pages(user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db)):
    return [{"id": p.id, "slug": p.slug, "title": p.title, "body": p.body, "seo_title": p.seo_title, "seo_description": p.seo_description,
             "is_published": p.is_published, "updated_at": p.updated_at.isoformat()} for p in db.scalars(select(CmsPage).order_by(CmsPage.slug)).all()]


@router.put("/pages/{slug}")
def upsert_page(slug: str, body: PageIn, request: Request, user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db)):
    p = db.scalar(select(CmsPage).where(CmsPage.slug == slug))
    if not p:
        p = CmsPage(slug=slugify(body.slug), title=body.title, body=body.body)
        db.add(p)
    for k, v in body.model_dump(exclude={"slug"}).items():
        setattr(p, k, v)
    audit(db, user, "page.upsert", "page", slug, {"title": body.title}, request_ip(request))
    db.commit()
    return {"slug": p.slug, "title": p.title}


@router.get("/settings")
def get_settings_admin(user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db)):
    out = []
    for key, (default, desc, public) in DEFAULT_SETTINGS.items():
        out.append({"key": key, "value": get_setting(db, key, default), "description": desc, "is_public": public})
    return out


class SettingsIn(BaseModel):
    values: dict[str, Any]


SENSITIVE_SETTINGS = {"free_shipping_threshold", "cod_fee", "cod_max_order_value", "allow_coupon_with_promotions", "gstin"}


@router.put("/settings")
def put_settings(body: SettingsIn, request: Request, user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db)):
    for key, value in body.values.items():
        if key not in DEFAULT_SETTINGS:
            raise ValidationFailed(f"Unknown setting: {key}")
        if key in SENSITIVE_SETTINGS and not user.has_permission("settings:write"):
            raise ValidationFailed(f"Only administrators can change {key}", code="forbidden")
        if key in ("free_shipping_threshold", "cod_fee", "cod_max_order_value"):
            try:
                if Decimal(str(value)) < 0:
                    raise ValueError
            except Exception:
                raise ValidationFailed(f"{key} must be a non-negative amount")
            value = f"{Decimal(str(value)):.2f}"
        set_setting(db, key, value)
    audit(db, user, "settings.update", "settings", None, body.values, request_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/newsletter")
def newsletter(user: User = Depends(require_permission("content:write")), db: Session = Depends(get_db), format: Literal["json", "csv"] = "json"):
    rows = db.scalars(select(NewsletterSubscriber).order_by(NewsletterSubscriber.id.desc())).all()
    data = [{"email": r.email, "status": r.status, "source": r.source, "subscribed_at": r.created_at.isoformat()} for r in rows]
    if format == "csv":
        return PlainTextResponse(report_service.to_csv(data), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="newsletter.csv"'})
    return data


# ================================================================== audit log
@router.get("/audit-logs")
def audit_logs(user: User = Depends(require_permission("audit:read")), db: Session = Depends(get_db), entity_type: str | None = None,
               action: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, le=200)):
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": a.id, "actor": a.actor_email or "system", "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
                       "changes": a.changes, "ip": a.ip_address, "at": a.created_at.isoformat()} for a in rows], **_page(total, page, page_size)}
