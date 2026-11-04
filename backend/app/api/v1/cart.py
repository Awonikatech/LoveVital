from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.core.errors import ValidationFailed
from app.core.rate_limit import rate_limit
from app.models import User
from app.schemas.common import AddressIn
from app.services import cart_service, order_service
from app.services.serializers import order_detail

router = APIRouter(tags=["cart & checkout"])


class CartItemIn(BaseModel):
    variant_id: int
    quantity: int = Field(default=1, ge=1, le=50)


class CartItemPatch(BaseModel):
    quantity: int = Field(ge=1, le=50)


class CouponIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)


def _cart(db: Session, user: User | None, token: str | None):
    return cart_service.get_cart(db, user, token)


@router.get("/cart", summary="Current cart (guest via X-Cart-Token header, or the logged-in user's cart)")
def get_cart(user: User | None = Depends(get_current_user_optional), x_cart_token: str | None = Header(default=None),
             db: Session = Depends(get_db)):
    cart = _cart(db, user, x_cart_token)
    db.commit()
    return cart_service.serialize_cart(db, cart, user)


@router.post("/cart/items", status_code=201)
def add_item(body: CartItemIn, user: User | None = Depends(get_current_user_optional),
             x_cart_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    cart = _cart(db, user, x_cart_token)
    cart_service.add_item(db, cart, body.variant_id, body.quantity)
    db.commit()
    return cart_service.serialize_cart(db, cart, user)


@router.patch("/cart/items/{item_id}")
def update_item(item_id: int, body: CartItemPatch, user: User | None = Depends(get_current_user_optional),
                x_cart_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    cart = _cart(db, user, x_cart_token)
    cart_service.update_item(db, cart, item_id, body.quantity)
    db.commit()
    return cart_service.serialize_cart(db, cart, user)


@router.delete("/cart/items/{item_id}")
def delete_item(item_id: int, user: User | None = Depends(get_current_user_optional),
                x_cart_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    cart = _cart(db, user, x_cart_token)
    cart_service.remove_item(db, cart, item_id)
    db.commit()
    return cart_service.serialize_cart(db, cart, user)


@router.post("/cart/coupon", dependencies=[Depends(rate_limit("coupon", 30, 300))])
def apply_coupon(body: CouponIn, user: User | None = Depends(get_current_user_optional),
                 x_cart_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    cart = _cart(db, user, x_cart_token)
    code = body.code.strip().upper()
    result, _ = cart_service.price(db, cart, user=user, coupon_code=code)
    if not result.coupon_applied:
        raise ValidationFailed(result.coupon_message or "Coupon could not be applied", code="coupon_invalid")
    cart.coupon_code = code
    db.commit()
    return cart_service.serialize_cart(db, cart, user)


@router.delete("/cart/coupon")
def remove_coupon(user: User | None = Depends(get_current_user_optional), x_cart_token: str | None = Header(default=None),
                  db: Session = Depends(get_db)):
    cart = _cart(db, user, x_cart_token)
    cart.coupon_code = None
    db.commit()
    return cart_service.serialize_cart(db, cart, user)


class CheckoutValidateIn(BaseModel):
    email: EmailStr | None = None
    pin_code: str | None = None
    shipping_method_id: int | None = None
    payment_method: Literal["razorpay", "cod"] = "razorpay"
    coupon_code: str | None = None


@router.post("/checkout/validate", summary="Server-side quote: totals, shipping options, COD eligibility, cart issues")
def checkout_validate(body: CheckoutValidateIn, user: User | None = Depends(get_current_user_optional),
                      x_cart_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    cart = _cart(db, user, x_cart_token)
    code = body.coupon_code if body.coupon_code is not None else cart.coupon_code
    quote = order_service.checkout_quote(db, cart, user=user, email=body.email or (user.email if user else None),
                                         pin=body.pin_code, shipping_method_id=body.shipping_method_id,
                                         payment_method=body.payment_method, coupon_code=code)
    db.commit()
    quote.pop("_result")
    quote.pop("_issues")
    quote["cart"] = cart_service.serialize_cart(db, cart, user)
    return quote


class CheckoutIn(BaseModel):
    email: EmailStr | None = Field(default=None, description="Required for guest checkout")
    phone: str | None = None
    shipping_address_id: int | None = None
    shipping_address: AddressIn | None = None
    billing_same_as_shipping: bool = True
    billing_address_id: int | None = None
    billing_address: AddressIn | None = None
    gstin: str | None = Field(default=None, pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
    save_address: bool = False
    shipping_method_id: int | None = None
    payment_method: Literal["razorpay", "cod"]
    coupon_code: str | None = None
    customer_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check(self):
        if not self.shipping_address_id and not self.shipping_address:
            raise ValueError("Shipping address is required")
        if not self.billing_same_as_shipping and not (self.billing_address_id or self.billing_address):
            raise ValueError("Billing address is required")
        return self


@router.post("/checkout", status_code=201, summary="Create order from cart (totals recalculated on the server)",
             dependencies=[Depends(rate_limit("checkout", 20, 300))])
def checkout(body: CheckoutIn, user: User | None = Depends(get_current_user_optional),
             x_cart_token: str | None = Header(default=None),
             idempotency_key: str | None = Header(default=None, max_length=64),
             db: Session = Depends(get_db)):
    if not user and not body.email:
        raise ValidationFailed("Email is required for guest checkout", code="email_required")
    cart = _cart(db, user, x_cart_token)
    ship = order_service.resolve_address(db, user, body.shipping_address_id, body.shipping_address.model_dump() if body.shipping_address else None)
    bill = None
    if not body.billing_same_as_shipping:
        bill = order_service.resolve_address(db, user, body.billing_address_id, body.billing_address.model_dump() if body.billing_address else None)
    if body.gstin:
        src = bill or ship
        fields = ("full_name", "phone", "line1", "line2", "landmark", "city", "state", "pin_code")
        bill = {**({k: src.get(k) for k in fields} if isinstance(src, dict) else {k: getattr(src, k) for k in fields}),
                "gstin": body.gstin}
    if user and body.save_address and body.shipping_address:
        from app.models import Address

        db.add(Address(user_id=user.id, **body.shipping_address.model_dump()))
    email = user.email if user else body.email
    phone = body.phone or (ship.phone if hasattr(ship, "phone") else ship.get("phone"))
    order, created = order_service.create_order(
        db, cart=cart, user=user, email=email, phone=phone, shipping_address=ship, billing_address=bill,
        shipping_method_id=body.shipping_method_id, payment_method=body.payment_method,
        coupon_code=body.coupon_code if body.coupon_code is not None else cart.coupon_code,
        customer_note=body.customer_note, idempotency_key=idempotency_key,
    )
    if created and order.payment_method == "cod":
        from app.services.notification_service import queue_order_email

        queue_order_email(order, "order_confirmed")
    db.commit()
    db.refresh(order)
    from app.api.v1.orders import order_key

    return {"created": created, "order": {**order_detail(order), "order_key": order_key(order)}}
