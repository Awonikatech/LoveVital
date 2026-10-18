"""Orders, payments, refunds, shipping and returns."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, IdMixin, TimestampMixin, utcnow

Money = Numeric(12, 2)


class ShippingMethod(IdMixin, TimestampMixin, Base):
    __tablename__ = "shipping_methods"
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    carrier: Mapped[str] = mapped_column(String(80), default="LoveVital Logistics (Mock)", nullable=False)
    base_charge: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    free_shipping_threshold: Mapped[Decimal | None] = mapped_column(Money)  # overrides store default
    min_days: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    max_days: Mapped[int] = mapped_column(SmallInteger, default=6, nullable=False)
    is_cod_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ServiceablePinCode(IdMixin, TimestampMixin, Base):
    """`pin_code` may be a full 6-digit PIN or a 3-digit prefix (fallback rule)."""

    __tablename__ = "serviceable_pin_codes"
    pin_code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(30), default="national", nullable=False)  # metro|regional|national|remote
    extra_days: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    is_serviceable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_cod_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Order(IdMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    order_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(30))
    payment_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)  # razorpay | cod
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal_mrp: Mapped[Decimal] = mapped_column(Money, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False)  # sum of sale prices
    item_discount_total: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)  # MRP - sale
    promotion_discount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    coupon_discount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    shipping_charge: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    cod_charge: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)  # GST included in prices
    grand_total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    refunded_total: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    applied_promotions: Mapped[list | None] = mapped_column(JSON)
    shipping_method_id: Mapped[int | None] = mapped_column(ForeignKey("shipping_methods.id", ondelete="SET NULL"))
    shipping_method_name: Mapped[str | None] = mapped_column(String(80))
    estimated_dispatch_date: Mapped[date | None] = mapped_column(Date)
    estimated_delivery_date: Mapped[date | None] = mapped_column(Date)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    customer_note: Mapped[str | None] = mapped_column(String(500))
    cancellation_reason: Mapped[str | None] = mapped_column(String(300))
    placed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    addresses: Mapped[list["OrderAddress"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order", order_by="Payment.id")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="order", order_by="Refund.id")
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="order", order_by="Shipment.id")
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order", order_by="OrderStatusHistory.id", cascade="all, delete-orphan"
    )
    notes: Mapped[list["OrderNote"]] = relationship(order_by="OrderNote.id", cascade="all, delete-orphan")
    user = relationship("User", lazy="joined")

    def address(self, kind: str) -> "OrderAddress | None":
        return next((a for a in self.addresses if a.address_type == kind), None)

    __table_args__ = (
        Index("ix_orders_status_placed", "status", "placed_at"),
        CheckConstraint("grand_total >= 0", name="ck_order_total_nonneg"),
    )


class OrderItem(IdMixin, Base):
    __tablename__ = "order_items"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id", ondelete="SET NULL"), index=True)
    # --- snapshots at purchase time ---
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_slug: Mapped[str | None] = mapped_column(String(220))
    variant_name: Mapped[str | None] = mapped_column(String(150))
    sku: Mapped[str] = mapped_column(String(60), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    attributes: Mapped[dict | None] = mapped_column(JSON)
    category_name: Mapped[str | None] = mapped_column(String(100))
    hsn_code: Mapped[str | None] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_mrp: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)  # promo + coupon allocated
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Money)
    returned_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_item_qty"),)


class OrderAddress(IdMixin, Base):
    __tablename__ = "order_addresses"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    address_type: Mapped[str] = mapped_column(String(10), nullable=False)  # shipping | billing
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255))
    landmark: Mapped[str | None] = mapped_column(String(150))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    pin_code: Mapped[str] = mapped_column(String(6), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15))

    order: Mapped[Order] = relationship(back_populates="addresses")

    __table_args__ = (UniqueConstraint("order_id", "address_type", name="uq_order_address_type"),)


class OrderStatusHistory(IdMixin, Base):
    __tablename__ = "order_status_history"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_type: Mapped[str] = mapped_column(String(20), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    order: Mapped[Order] = relationship(back_populates="history")


class OrderNote(IdMixin, Base):
    __tablename__ = "order_notes"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    author_name: Mapped[str | None] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Payment(IdMixin, TimestampMixin, Base):
    """Amounts are stored in paise (smallest INR unit) as integers: paise = round(rupees * 100)."""

    __tablename__ = "payments"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="razorpay", nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # mock | test | live
    method: Mapped[str | None] = mapped_column(String(30))  # upi | card | netbanking | wallet | cod
    razorpay_order_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    razorpay_signature: Mapped[str | None] = mapped_column(String(128))
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_refunded_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    # created | captured | failed | refunded | partially_refunded | cod_pending | cod_collected
    status: Mapped[str] = mapped_column(String(30), default="created", nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_description: Mapped[str | None] = mapped_column(String(300))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime)

    order: Mapped[Order] = relationship(back_populates="payments")

    __table_args__ = (CheckConstraint("amount_paise >= 0", name="ck_payment_amount_nonneg"),)


class PaymentEvent(IdMixin, Base):
    __tablename__ = "payment_events"
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"), index=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # idempotency key
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # webhook | verify | system
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    processing_result: Mapped[str] = mapped_column(String(30), default="received", nullable=False)
    error: Mapped[str | None] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Refund(IdMixin, TimestampMixin, Base):
    __tablename__ = "refunds"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"), index=True)
    razorpay_refund_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending|processed|failed
    reason: Mapped[str | None] = mapped_column(String(300))
    initiated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    order: Mapped[Order] = relationship(back_populates="refunds")

    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_refund_amount_pos"),)


class Shipment(IdMixin, TimestampMixin, Base):
    __tablename__ = "shipments"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)
    courier_name: Mapped[str | None] = mapped_column(String(80))
    tracking_number: Mapped[str | None] = mapped_column(String(60), unique=True)
    tracking_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    estimated_delivery_date: Mapped[date | None] = mapped_column(Date)

    order: Mapped[Order] = relationship(back_populates="shipments")
    events: Mapped[list["ShipmentEvent"]] = relationship(
        back_populates="shipment", order_by="ShipmentEvent.occurred_at", cascade="all, delete-orphan"
    )


class ShipmentEvent(IdMixin, Base):
    __tablename__ = "shipment_events"
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    shipment: Mapped[Shipment] = relationship(back_populates="events")


class ReturnRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "returns"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    return_type: Mapped[str] = mapped_column(String(20), default="return", nullable=False)  # return | replacement
    # requested | approved | rejected | received | refunded | completed
    status: Mapped[str] = mapped_column(String(20), default="requested", nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list] = mapped_column(JSON, nullable=False)  # [{order_item_id, quantity}]
    refund_amount: Mapped[Decimal | None] = mapped_column(Money)
    admin_note: Mapped[str | None] = mapped_column(String(500))
    refund_id: Mapped[int | None] = mapped_column(ForeignKey("refunds.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    order = relationship("Order", lazy="joined")
