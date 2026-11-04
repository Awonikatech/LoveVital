"""Pluggable shipping provider. Implement `ShippingProvider` for a real courier
(Shiprocket, Delhivery, Blue Dart...) and register it in `get_shipping_provider`."""
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

from app.core.config import settings


@dataclass
class CreatedShipment:
    tracking_number: str
    tracking_url: str
    courier_name: str


@dataclass
class TrackingEvent:
    status: str
    location: str
    description: str
    occurred_at: datetime


class ShippingProvider(Protocol):
    name: str

    def create_shipment(self, order_number: str, pin_code: str, weight_grams: int, method_code: str) -> CreatedShipment: ...
    def tracking_events(self, tracking_number: str, status: str, shipped_at: datetime | None, dest_city: str) -> list[TrackingEvent]: ...


class MockShippingProvider:
    """Generates realistic AWB numbers and a plausible tracking timeline for the current status."""

    name = "mock"
    couriers = {"standard": "BlueRiver Express", "express": "Swift Air Couriers", "same_day": "Metro Dash"}
    hubs = ["Delhi Gateway Hub", "Gurugram Sortation Centre", "Mumbai Air Hub", "Bengaluru Mother Hub", "Kolkata Hub"]

    def create_shipment(self, order_number: str, pin_code: str, weight_grams: int, method_code: str) -> CreatedShipment:
        awb = f"SWK{secrets.randbelow(10**9):09d}IN"
        return CreatedShipment(
            tracking_number=awb,
            tracking_url=f"{settings.FRONTEND_URL}/track/{awb}",
            courier_name=self.couriers.get(method_code, "BlueRiver Express"),
        )

    def tracking_events(self, tracking_number: str, status: str, shipped_at: datetime | None, dest_city: str) -> list[TrackingEvent]:
        base = shipped_at or datetime.utcnow()
        hub = self.hubs[int(tracking_number[3:12] or 0) % len(self.hubs)] if tracking_number[3:12].isdigit() else self.hubs[0]
        timeline = [
            ("shipped", "Noida Fulfilment Centre", "Shipment picked up by courier", 0),
            ("in_transit", hub, "Arrived at sorting hub", 10),
            ("in_transit", hub, "Departed sorting hub", 16),
            ("in_transit", f"{dest_city} Delivery Centre", "Arrived at destination delivery centre", 34),
            ("out_for_delivery", dest_city, "Out for delivery with our delivery partner", 44),
            ("delivered", dest_city, "Delivered. Thank you for shopping with LoveVital!", 50),
        ]
        upto = {"shipped": 3, "in_transit": 4, "out_for_delivery": 5, "delivered": 6, "delivery_failed": 5}.get(status, 1)
        events = [TrackingEvent(s, loc, d, base + timedelta(hours=h)) for s, loc, d, h in timeline[:upto]]
        if status == "delivery_failed":
            events.append(
                TrackingEvent("delivery_failed", dest_city, "Delivery attempted — customer unavailable", base + timedelta(hours=50))
            )
        return events


def get_shipping_provider() -> ShippingProvider:
    return MockShippingProvider()


def add_business_days(start: date, days: int) -> date:
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() != 6:  # couriers deliver Mon–Sat
            added += 1
    return d
