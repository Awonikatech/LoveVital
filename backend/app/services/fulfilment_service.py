"""Shipments and tracking (works with any ShippingProvider adapter)."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.errors import Conflict, NotFound
from app.integrations.shipping import get_shipping_provider
from app.models import Order, Shipment, ShipmentEvent, ShippingMethod, User
from app.services import order_service
from app.services.notification_service import queue_order_email

SHIPMENT_TO_ORDER = {"shipped": "shipped", "in_transit": None, "out_for_delivery": "out_for_delivery",
                     "delivered": "delivered", "delivery_failed": "delivery_failed"}


def create_shipment(db: Session, order: Order, actor: User, courier_name: str | None = None,
                    tracking_number: str | None = None, tracking_url: str | None = None, weight_grams: int | None = None) -> Shipment:
    if order.status not in ("processing", "packed", "delivery_failed"):
        raise Conflict("Shipments can be created for processing/packed orders only", code="invalid_state")
    if any(s.status not in ("cancelled", "returned") for s in order.shipments) and order.status != "delivery_failed":
        raise Conflict("This order already has an active shipment")
    ship_addr = order.address("shipping")
    method = db.get(ShippingMethod, order.shipping_method_id) if order.shipping_method_id else None
    provider = get_shipping_provider()
    if not tracking_number:
        created = provider.create_shipment(order.order_number, ship_addr.pin_code, weight_grams or 250, method.code if method else "standard")
        tracking_number, tracking_url, courier_name = created.tracking_number, created.tracking_url, courier_name or created.courier_name
    if db.scalar(select(Shipment.id).where(Shipment.tracking_number == tracking_number)):
        raise Conflict("Tracking number already used on another shipment")
    s = Shipment(order_id=order.id, provider=provider.name, courier_name=courier_name or "Courier", tracking_number=tracking_number,
                 tracking_url=tracking_url, status="ready", weight_grams=weight_grams, estimated_delivery_date=order.estimated_delivery_date)
    db.add(s)
    order.shipments.append(s)
    db.flush()
    if order.status == "processing":
        order_service.transition(db, order, "packed", actor=actor, note="Packed for dispatch")
    return s


def update_shipment_status(db: Session, shipment: Shipment, status: str, actor: User | None, location: str | None = None,
                           description: str | None = None) -> Shipment:
    order = shipment.order
    target = SHIPMENT_TO_ORDER.get(status, "invalid")
    if target == "invalid":
        raise Conflict("Unknown shipment status")
    now = utcnow()
    if target and target != order.status:
        order_service.transition(db, order, target, actor=actor, note=description or f"Shipment {status.replace('_', ' ')}")
    shipment.status = status
    if status == "shipped":
        shipment.shipped_at = shipment.shipped_at or now
        queue_order_email(order, "order_shipped")
    if status == "delivered":
        shipment.delivered_at = now
        queue_order_email(order, "order_delivered")
    city = order.address("shipping").city
    default_desc = {
        "shipped": "Shipment picked up by courier", "in_transit": "In transit", "out_for_delivery": "Out for delivery",
        "delivered": "Delivered", "delivery_failed": "Delivery attempt failed",
    }[status]
    db.add(ShipmentEvent(shipment_id=shipment.id, status=status, location=location or city, description=description or default_desc, occurred_at=now))
    db.flush()
    return shipment


def tracking_payload(db: Session, shipment: Shipment) -> dict:
    order = shipment.order
    events = list(shipment.events)
    if not events and shipment.status not in ("ready", "pending"):
        dest = order.address("shipping").city
        events = get_shipping_provider().tracking_events(shipment.tracking_number or "", shipment.status, shipment.shipped_at, dest)
    return {
        "order_number": order.order_number,
        "order_status": order.status,
        "order_status_label": order_service.STATUS_LABELS.get(order.status, order.status),
        "courier_name": shipment.courier_name,
        "tracking_number": shipment.tracking_number,
        "tracking_url": shipment.tracking_url,
        "status": shipment.status,
        "shipped_at": shipment.shipped_at,
        "delivered_at": shipment.delivered_at,
        "estimated_delivery_date": shipment.estimated_delivery_date,
        "destination": f"{order.address('shipping').city}, {order.address('shipping').state}",
        "events": [
            {"status": e.status, "location": e.location, "description": e.description,
             "occurred_at": e.occurred_at.isoformat() if isinstance(e.occurred_at, datetime) else e.occurred_at}
            for e in sorted(events, key=lambda e: e.occurred_at, reverse=True)
        ],
    }


def find_by_tracking(db: Session, awb: str) -> Shipment:
    s = db.scalar(select(Shipment).where(Shipment.tracking_number == awb))
    if not s:
        raise NotFound("No shipment found with that tracking number")
    return s
