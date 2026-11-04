"""Admin order management, shipments, refunds and returns."""
import csv
import io
import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db, utcnow
from app.core.deps import request_ip, require_permission
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import Order, OrderAddress, OrderNote, ReturnRequest, Shipment, User
from app.services import fulfilment_service, invoice_service, order_service, payment_service
from app.services.common import audit
from app.services.notification_service import queue_order_email
from app.services.serializers import order_detail, order_summary

router = APIRouter(tags=["admin: orders"])


def _order(db: Session, oid: int, lock: bool = False) -> Order:
    stmt = select(Order).where(Order.id == oid)
    if lock:
        stmt = stmt.with_for_update()
    o = db.scalar(stmt)
    if not o:
        raise NotFound("Order not found")
    return o


def _filtered(db: Session, q: str | None, status: str | None, payment_status: str | None, payment_method: str | None,
              date_from: date | None, date_to: date | None):
    stmt = select(Order)
    if q:
        like = f"%{q.strip().lower()}%"
        sub = select(OrderAddress.order_id).where(func.lower(OrderAddress.full_name).like(like))
        stmt = stmt.where(or_(func.lower(Order.order_number).like(like), func.lower(Order.email).like(like), Order.phone.like(like), Order.id.in_(sub)))
    if status:
        stmt = stmt.where(Order.status.in_(status.split(",")))
    if payment_status:
        stmt = stmt.where(Order.payment_status.in_(payment_status.split(",")))
    if payment_method:
        stmt = stmt.where(Order.payment_method == payment_method)
    if date_from:
        stmt = stmt.where(Order.placed_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(Order.placed_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    return stmt


@router.get("/orders")
def list_orders(user: User = Depends(require_permission("orders:read")), db: Session = Depends(get_db), q: str | None = None,
                status: str | None = None, payment_status: str | None = None, payment_method: str | None = None,
                date_from: date | None = None, date_to: date | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, le=100)):
    stmt = _filtered(db, q, status, payment_status, payment_method, date_from, date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Order.placed_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    counts = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    return {"items": [order_summary(o) for o in rows], "total": total, "page": page, "page_size": page_size,
            "pages": math.ceil(total / page_size) if total else 0, "status_counts": counts}


@router.get("/orders-export.csv")
def export_orders(user: User = Depends(require_permission("orders:read")), db: Session = Depends(get_db), q: str | None = None,
                  status: str | None = None, payment_status: str | None = None, payment_method: str | None = None,
                  date_from: date | None = None, date_to: date | None = None):
    rows = db.scalars(_filtered(db, q, status, payment_status, payment_method, date_from, date_to).order_by(Order.placed_at.desc())).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["order_number", "placed_at", "status", "payment_status", "payment_method", "customer", "email", "phone", "city", "state",
                "pin_code", "items", "subtotal_mrp", "subtotal", "promotion_discount", "coupon_code", "coupon_discount", "shipping", "cod_fee",
                "gst_included", "grand_total", "refunded"])
    for o in rows:
        a = o.address("shipping")
        w.writerow([o.order_number, o.placed_at.isoformat(), o.status, o.payment_status, o.payment_method, a.full_name if a else "", o.email,
                    o.phone or "", a.city if a else "", a.state if a else "", a.pin_code if a else "", sum(i.quantity for i in o.items),
                    o.subtotal_mrp, o.subtotal, o.promotion_discount, o.coupon_code or "", o.coupon_discount, o.shipping_charge, o.cod_charge,
                    o.tax_total, o.grand_total, o.refunded_total])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="orders-{utcnow():%Y%m%d}.csv"'})


@router.get("/orders/{oid}")
def get_order(oid: int, user: User = Depends(require_permission("orders:read")), db: Session = Depends(get_db)):
    o = _order(db, oid)
    d = order_detail(o, admin=True)
    if not user.has_permission("products:cost"):
        for it in d["items"]:
            it.pop("unit_cost", None)
    d["manual_transitions"] = [t for t in d["allowed_transitions"] if t["value"] in order_service.ADMIN_MANUAL_TARGETS]
    d["can_refund"] = user.has_permission("refunds:write") and o.payment_status in ("paid", "partially_refunded")
    d["can_ship"] = o.status in ("processing", "packed", "delivery_failed")
    return d


class StatusIn(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=300)


@router.post("/orders/{oid}/status")
def change_status(oid: int, body: StatusIn, request: Request, user: User = Depends(require_permission("orders:write")), db: Session = Depends(get_db)):
    o = _order(db, oid, lock=True)
    if body.status not in order_service.ADMIN_MANUAL_TARGETS:
        raise ValidationFailed("Use the dedicated action (ship, cancel, refund, return) for this status", code="use_dedicated_action")
    frm = o.status
    if body.status in ("out_for_delivery", "delivered", "delivery_failed") and o.shipments:
        fulfilment_service.update_shipment_status(db, o.shipments[-1], body.status, user, description=body.note)
    else:
        order_service.transition(db, o, body.status, actor=user, note=body.note)
    audit(db, user, "order.status", "order", o.id, {"from": frm, "to": o.status, "note": body.note}, request_ip(request))
    db.commit()
    return order_detail(o, admin=True)


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/orders/{oid}/cancel")
def admin_cancel(oid: int, body: CancelIn, request: Request, user: User = Depends(require_permission("orders:write")), db: Session = Depends(get_db)):
    o = _order(db, oid, lock=True)
    if o.payment_status == "paid" and not user.has_permission("refunds:write"):
        raise ValidationFailed("Cancelling a paid order triggers a refund; an administrator must do this", code="refund_permission_required")
    order_service.cancel(db, o, actor=user, reason=body.reason, actor_type="admin")
    queue_order_email(o, "order_cancelled")
    audit(db, user, "order.cancel", "order", o.id, {"reason": body.reason}, request_ip(request))
    db.commit()
    return order_detail(o, admin=True)


class ResolveIn(BaseModel):
    approve: bool
    note: str | None = None


@router.post("/orders/{oid}/cancellation-request")
def resolve_cancellation(oid: int, body: ResolveIn, request: Request, user: User = Depends(require_permission("orders:write")), db: Session = Depends(get_db)):
    o = _order(db, oid, lock=True)
    order_service.resolve_cancellation_request(db, o, body.approve, user, body.note)
    if body.approve:
        queue_order_email(o, "order_cancelled")
    audit(db, user, "order.cancellation_request", "order", o.id, body.model_dump(), request_ip(request))
    db.commit()
    return order_detail(o, admin=True)


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.post("/orders/{oid}/notes", status_code=201)
def add_note(oid: int, body: NoteIn, user: User = Depends(require_permission("orders:write")), db: Session = Depends(get_db)):
    o = _order(db, oid)
    db.add(OrderNote(order_id=o.id, author_id=user.id, author_name=user.full_name, body=body.body))
    db.commit()
    db.refresh(o)
    return order_detail(o, admin=True)["notes"]


class ShipmentIn(BaseModel):
    courier_name: str | None = Field(default=None, max_length=80)
    tracking_number: str | None = Field(default=None, max_length=60)
    tracking_url: str | None = Field(default=None, max_length=500)
    weight_grams: int | None = Field(default=None, ge=1)
    mark_shipped: bool = True


@router.post("/orders/{oid}/shipments", status_code=201)
def create_shipment(oid: int, body: ShipmentIn, request: Request, user: User = Depends(require_permission("orders:write")), db: Session = Depends(get_db)):
    o = _order(db, oid, lock=True)
    s = fulfilment_service.create_shipment(db, o, user, body.courier_name, body.tracking_number, body.tracking_url, body.weight_grams)
    if body.mark_shipped:
        fulfilment_service.update_shipment_status(db, s, "shipped", user)
    audit(db, user, "order.shipment", "order", o.id, {"tracking": s.tracking_number, "courier": s.courier_name}, request_ip(request))
    db.commit()
    return order_detail(o, admin=True)


class ShipmentStatusIn(BaseModel):
    status: Literal["shipped", "in_transit", "out_for_delivery", "delivered", "delivery_failed"]
    location: str | None = None
    description: str | None = None


@router.post("/shipments/{sid}/status")
def shipment_status(sid: int, body: ShipmentStatusIn, request: Request, user: User = Depends(require_permission("orders:write")), db: Session = Depends(get_db)):
    s = db.get(Shipment, sid)
    if not s:
        raise NotFound("Shipment not found")
    fulfilment_service.update_shipment_status(db, s, body.status, user, body.location, body.description)
    audit(db, user, "shipment.status", "shipment", s.id, body.model_dump(), request_ip(request))
    db.commit()
    return order_detail(s.order, admin=True)


class RefundIn(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, description="Leave empty for full remaining amount")
    reason: str = Field(min_length=3, max_length=300)


@router.post("/orders/{oid}/refunds", status_code=201)
def refund(oid: int, body: RefundIn, request: Request, user: User = Depends(require_permission("refunds:write")), db: Session = Depends(get_db)):
    o = _order(db, oid, lock=True)
    r = payment_service.refund_order(db, o, amount=body.amount, reason=body.reason, actor=user)
    audit(db, user, "order.refund", "order", o.id, {"amount_paise": r.amount_paise, "reason": body.reason, "refund_id": r.id}, request_ip(request))
    db.commit()
    return order_detail(o, admin=True)


@router.get("/orders/{oid}/invoice", response_class=Response)
def invoice(oid: int, user: User = Depends(require_permission("orders:read")), db: Session = Depends(get_db)):
    o = _order(db, oid)
    return Response(invoice_service.invoice_pdf(db, o), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="Invoice-{o.order_number}.pdf"'})


@router.get("/orders/{oid}/packing-slip", response_class=Response)
def packing_slip(oid: int, user: User = Depends(require_permission("orders:read")), db: Session = Depends(get_db)):
    o = _order(db, oid)
    return Response(invoice_service.packing_slip_pdf(db, o), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="PackingSlip-{o.order_number}.pdf"'})


# ------------------------------------------------------------------ returns
def _rr(r: ReturnRequest) -> dict:
    by_id = {i.id: i for i in r.order.items}
    return {"id": r.id, "order_id": r.order_id, "order_number": r.order.order_number, "customer_email": r.order.email,
            "return_type": r.return_type, "status": r.status, "reason": r.reason, "details": r.details,
            "items": [{"order_item_id": x["order_item_id"], "quantity": x["quantity"], "product_name": by_id[x["order_item_id"]].product_name if x["order_item_id"] in by_id else "?",
                       "sku": by_id[x["order_item_id"]].sku if x["order_item_id"] in by_id else "", "image_url": by_id[x["order_item_id"]].image_url if x["order_item_id"] in by_id else None}
                      for x in r.items],
            "refund_amount": f"{r.refund_amount:.2f}" if r.refund_amount is not None else None, "admin_note": r.admin_note,
            "created_at": r.created_at.isoformat(), "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "order_status": r.order.status, "payment_method": r.order.payment_method}


@router.get("/returns")
def list_returns(user: User = Depends(require_permission("returns:read")), db: Session = Depends(get_db), status: str | None = None,
                 page: int = Query(1, ge=1), page_size: int = Query(20, le=100)):
    stmt = select(ReturnRequest)
    if status:
        stmt = stmt.where(ReturnRequest.status.in_(status.split(",")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(ReturnRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_rr(r) for r in rows], "total": total, "page": page, "page_size": page_size, "pages": math.ceil(total / page_size) if total else 0}


class ReturnActionIn(BaseModel):
    action: Literal["approve", "reject", "receive"]
    note: str | None = Field(default=None, max_length=500)


@router.post("/returns/{rid}")
def return_action(rid: int, body: ReturnActionIn, request: Request, user: User = Depends(require_permission("returns:write")), db: Session = Depends(get_db)):
    r = db.get(ReturnRequest, rid)
    if not r:
        raise NotFound("Return request not found")
    if body.action == "receive" and r.return_type == "return" and r.order.payment_status in ("paid", "partially_refunded") \
            and not user.has_permission("refunds:write"):
        raise ValidationFailed("Receiving this return issues a refund; an administrator must complete it", code="refund_permission_required")
    order_service.resolve_return(db, r, body.action, user, body.note)
    audit(db, user, f"return.{body.action}", "return", r.id, body.model_dump(), request_ip(request))
    db.commit()
    return _rr(r)
