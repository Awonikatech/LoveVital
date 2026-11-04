"""Delivery estimation & PIN-code serviceability.

Estimate = today + processing_days (dispatch, business days)
         + method.min_days..max_days + PIN rule extra_days (delivery, business days, Mon–Sat).
PIN rules: exact 6-digit row first, then a 3-digit prefix row; otherwise serviceable at national
defaults with +2 days (configurable by adding rows). A row with is_serviceable = false blocks delivery."""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.errors import NotFound, ValidationFailed
from app.integrations.shipping import add_business_days
from app.models import ServiceablePinCode, ShippingMethod
from app.schemas.common import PIN_RE


@dataclass
class PinRule:
    serviceable: bool
    cod: bool
    extra_days: int
    region: str
    city: str | None
    state: str | None


def pin_rule(db: Session, pin: str) -> PinRule:
    if not PIN_RE.match(pin or ""):
        raise ValidationFailed("Enter a valid 6-digit PIN code", code="invalid_pin")
    row = db.scalar(select(ServiceablePinCode).where(ServiceablePinCode.pin_code == pin))
    if row is None:
        row = db.scalar(select(ServiceablePinCode).where(ServiceablePinCode.pin_code == pin[:3]))
    if row is None:
        return PinRule(True, True, 2, "national", None, None)
    return PinRule(row.is_serviceable, row.is_cod_available and row.is_serviceable, row.extra_days, row.region, row.city, row.state)


def active_methods(db: Session) -> list[ShippingMethod]:
    return list(db.scalars(select(ShippingMethod).where(ShippingMethod.is_active.is_(True)).order_by(ShippingMethod.display_order)))


def get_method(db: Session, method_id: int | None) -> ShippingMethod:
    if method_id:
        m = db.get(ShippingMethod, method_id)
        if not m or not m.is_active:
            raise NotFound("Shipping method not available", code="invalid_shipping_method")
        return m
    methods = active_methods(db)
    if not methods:
        raise NotFound("No shipping methods configured", code="no_shipping_methods")
    return methods[0]


def estimate_dates(method: ShippingMethod, rule: PinRule, processing_days: int, start: date | None = None) -> tuple[date, date, date]:
    start = start or utcnow().date()
    dispatch = add_business_days(start, max(0, processing_days))
    earliest = add_business_days(dispatch, method.min_days + rule.extra_days)
    latest = add_business_days(dispatch, method.max_days + rule.extra_days)
    return dispatch, earliest, latest


def estimate(db: Session, pin: str, processing_days: int = 1, order_value=None, free_threshold=None) -> dict:
    rule = pin_rule(db, pin)
    out = {
        "pin_code": pin,
        "serviceable": rule.serviceable,
        "cod_available": rule.cod,
        "region": rule.region,
        "city": rule.city,
        "state": rule.state,
        "methods": [],
    }
    if not rule.serviceable:
        out["message"] = "Sorry, we don't deliver to this PIN code yet."
        return out
    for m in active_methods(db):
        dispatch, earliest, latest = estimate_dates(m, rule, processing_days)
        threshold = m.free_shipping_threshold if m.free_shipping_threshold is not None else free_threshold
        free = threshold is not None and order_value is not None and order_value >= threshold
        out["methods"].append({
            "id": m.id,
            "code": m.code,
            "name": m.name,
            "carrier": m.carrier,
            "description": m.description,
            "charge": "0.00" if free else f"{m.base_charge:.2f}",
            "base_charge": f"{m.base_charge:.2f}",
            "free_shipping_threshold": f"{threshold:.2f}" if threshold is not None else None,
            "is_cod_allowed": m.is_cod_allowed and rule.cod,
            "dispatch_date": dispatch.isoformat(),
            "delivery_from": earliest.isoformat(),
            "delivery_to": latest.isoformat(),
            "min_days": m.min_days + rule.extra_days,
            "max_days": m.max_days + rule.extra_days,
        })
    m0 = out["methods"][0] if out["methods"] else None
    out["message"] = (
        f"Delivery by {date.fromisoformat(m0['delivery_from']).strftime('%a, %d %b')} – "
        f"{date.fromisoformat(m0['delivery_to']).strftime('%a, %d %b')}" if m0 else "No delivery options"
    )
    return out
