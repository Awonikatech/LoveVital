import math
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_optional
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.rate_limit import rate_limit
from app.core.security import constant_time_equals, hmac_sha256_hex
from app.models import Order, ReturnRequest, User
from app.services import fulfilment_service, invoice_service, order_service, payment_service
from app.services.serializers import order_detail, order_summary

router = APIRouter(tags=["orders & payments"])


def order_key(order: Order) -> str:
    """Capability token that lets a guest view/pay for their own order without an account."""
    return hmac_sha256_hex(settings.SECRET_KEY, f"order:{order.id}:{order.email}")[:32]


def _load_order(db: Session, ref: str) -> Order | None:
    stmt = select(Order).where(Order.order_number == ref) if not ref.isdigit() else select(Order).where(Order.id == int(ref))
    return db.scalar(stmt)


def authorize_order(db: Session, ref: str, user: User | None, key: str | None) -> Order:
    order = _load_order(db, ref)
    if not order:
        raise NotFound("Order not found")
    if user and (order.user_id == user.id or user.is_staff):
        return order
    if key and constant_time_equals(order_key(order), key):
        return order
    if not user and not key:
        raise NotFound("Order not found")
    raise Forbidden("You don't have access to this order")


def _detail(order: Order, include_key: bool = False) -> dict:
    d = order_detail(order)
    if include_key:
        d["order_key"] = order_key(order)
    return d


# ------------------------------------------------------------------ customer orders
@router.get("/orders")
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db), page: int = Query(1, ge=1),
              page_size: int = Query(10, le=50), status: str | None = None):
    stmt = select(Order).where(Order.user_id == user.id)
    if status:
        stmt = stmt.where(Order.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Order.placed_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [order_summary(o) for o in rows], "total": total, "page": page, "page_size": page_size,
            "pages": math.ceil(total / page_size) if total else 0}


@router.get("/orders/{order_ref}")
def get_order(order_ref: str, key: str | None = None, user: User | None = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    order = authorize_order(db, order_ref, user, key)
    return _detail(order, include_key=True)


class LookupIn(BaseModel):
    order_number: str = Field(min_length=5, max_length=30)
    email: EmailStr


@router.post("/orders/lookup", summary="Guest order lookup by order number + email",
             dependencies=[Depends(rate_limit("lookup", 15, 600))])
def lookup(body: LookupIn, db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.order_number == body.order_number.strip().upper()))
    if not order or order.email.lower() != body.email.lower():
        raise NotFound("We couldn't find an order with those details")
    return _detail(order, include_key=True)


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/orders/{order_ref}/cancel")
def cancel_order(order_ref: str, body: CancelIn, key: str | None = None, user: User | None = Depends(get_current_user_optional),
                 db: Session = Depends(get_db)):
    order = authorize_order(db, order_ref, user, key)
    order = db.scalar(select(Order).where(Order.id == order.id).with_for_update())
    status = order_service.cancel(db, order, actor=user, reason=body.reason, actor_type="customer")
    # A paid order moves on from "cancelled" to "refund_initiated"/"refunded" within the same call.
    cancelled = status != "cancellation_requested"
    if cancelled:
        from app.services.notification_service import queue_order_email

        queue_order_email(order, "order_cancelled")
    db.commit()
    msg = "Your order has been cancelled." if cancelled else "Cancellation requested. We'll confirm shortly."
    if order.payment_status in ("refunded", "partially_refunded"):
        msg += " A refund has been initiated to your original payment method."
    return {"message": msg, "order": _detail(order)}


class ReturnItemIn(BaseModel):
    order_item_id: int
    quantity: int = Field(ge=1)


class ReturnIn(BaseModel):
    return_type: Literal["return", "replacement"] = "return"
    reason: Literal["damaged", "wrong_item", "size_issue", "quality_issue", "not_as_described", "changed_mind", "other"]
    details: str | None = Field(default=None, max_length=1000)
    items: list[ReturnItemIn] = Field(min_length=1)


@router.post("/orders/{order_ref}/returns", status_code=201)
def create_return(order_ref: str, body: ReturnIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = authorize_order(db, order_ref, user, None)
    if order.user_id != user.id:
        raise Forbidden("Not your order")
    rr = order_service.request_return(db, order, user, [i.model_dump() for i in body.items], body.reason, body.details, body.return_type)
    db.commit()
    return {"message": "Return request submitted. We'll review it within 24–48 hours.", "return_id": rr.id, "order": _detail(order)}


@router.get("/returns")
def my_returns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ReturnRequest).where(ReturnRequest.user_id == user.id).order_by(ReturnRequest.created_at.desc())).all()
    return [{"id": r.id, "order_number": r.order.order_number, "return_type": r.return_type, "status": r.status, "reason": r.reason,
             "refund_amount": f"{r.refund_amount:.2f}" if r.refund_amount is not None else None, "items": r.items,
             "admin_note": r.admin_note, "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/orders/{order_ref}/invoice", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def invoice(order_ref: str, key: str | None = None, user: User | None = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    order = authorize_order(db, order_ref, user, key)
    if order.payment_status not in ("paid", "partially_refunded", "refunded") and order.payment_method != "cod":
        raise ValidationFailed("Invoice is available once payment is confirmed")
    pdf = invoice_service.invoice_pdf(db, order)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="LoveVital-Invoice-{order.order_number}.pdf"'})


@router.get("/track/{awb}", summary="Public shipment tracking by AWB / tracking number")
def track(awb: str, db: Session = Depends(get_db)):
    s = fulfilment_service.find_by_tracking(db, awb.strip().upper())
    return fulfilment_service.tracking_payload(db, s)


# ------------------------------------------------------------------ payments
class CreatePaymentIn(BaseModel):
    order_id: str
    order_key: str | None = None


@router.post("/payments/razorpay/create-order", summary="Create (or reuse) a Razorpay order for an unpaid order",
             dependencies=[Depends(rate_limit("pay_create", 30, 300))])
def create_payment(body: CreatePaymentIn, user: User | None = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    order = authorize_order(db, body.order_id, user, body.order_key)
    data = payment_service.create_payment_order(db, order)
    db.commit()
    return data


class VerifyIn(BaseModel):
    razorpay_order_id: str = Field(max_length=64)
    razorpay_payment_id: str = Field(max_length=64)
    razorpay_signature: str = Field(max_length=128)


@router.post("/payments/razorpay/verify", summary="Verify checkout signature server-side and confirm the order",
             dependencies=[Depends(rate_limit("pay_verify", 30, 300))])
def verify(body: VerifyIn, db: Session = Depends(get_db)):
    order = payment_service.verify_payment(db, body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature)
    db.commit()
    return {"status": "paid" if order.payment_status in ("paid",) else order.payment_status, "order_number": order.order_number,
            "order": _detail(order, include_key=True)}


class FailureIn(BaseModel):
    razorpay_order_id: str = Field(max_length=64)
    razorpay_payment_id: str | None = Field(default=None, max_length=64)
    error_code: str | None = Field(default=None, max_length=80)
    error_description: str | None = Field(default=None, max_length=300)


@router.post("/payments/razorpay/failed", summary="Report a checkout failure (confirmed with the gateway before use)")
def failed(body: FailureIn, db: Session = Depends(get_db)):
    order = payment_service.report_failure(db, body.razorpay_order_id, body.razorpay_payment_id, body.error_code, body.error_description)
    db.commit()
    return {"status": order.payment_status, "order_number": order.order_number, "order_key": order_key(order)}


@router.post("/payments/razorpay/webhook", summary="Razorpay webhook (signature-verified, idempotent)")
async def webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    return payment_service.handle_webhook(db, raw, request.headers.get("x-razorpay-signature"), request.headers.get("x-razorpay-event-id"))


@router.get("/payments/status/{order_ref}")
def payment_status(order_ref: str, key: str | None = None, user: User | None = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    order = authorize_order(db, order_ref, user, key)
    last = order.payments[-1] if order.payments else None
    return {"order_number": order.order_number, "order_status": order.status, "payment_status": order.payment_status,
            "grand_total": f"{order.grand_total:.2f}", "last_error": last.error_description if last else None,
            "can_retry": order.status == "payment_pending" and order.payment_status != "paid"}


class MockCheckoutIn(BaseModel):
    razorpay_order_id: str
    outcome: Literal["success", "failure"] = "success"
    method: Literal["upi", "card", "netbanking", "wallet"] = "upi"


@router.post("/payments/razorpay/mock-checkout", summary="[mock mode only] Simulate the Razorpay checkout popup")
def mock_checkout(body: MockCheckoutIn, db: Session = Depends(get_db)):
    if settings.RAZORPAY_MODE != "mock":
        raise NotFound("Not available")
    return payment_service.mock_checkout(db, body.razorpay_order_id, body.outcome == "success", body.method)
