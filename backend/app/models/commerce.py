"""Inventory, carts, wishlists, coupons and promotions."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, IdMixin, TimestampMixin, utcnow

Money = Numeric(12, 2)


class Inventory(IdMixin, TimestampMixin, Base):
    __tablename__ = "inventory"
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    variant = relationship("ProductVariant", back_populates="inventory")

    @property
    def available(self) -> int:
        return max(0, self.quantity_on_hand - self.quantity_reserved)

    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="ck_inv_on_hand_nonneg"),
        CheckConstraint("quantity_reserved >= 0", name="ck_inv_reserved_nonneg"),
    )


class InventoryMovement(IdMixin, Base):
    __tablename__ = "inventory_movements"
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # initial | restock | sale | return | adjustment | damage | cancellation
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # signed
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[str | None] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)

    variant = relationship("ProductVariant", lazy="joined")


class InventoryReservation(IdMixin, TimestampMixin, Base):
    __tablename__ = "inventory_reservations"
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active|committed|released
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    release_reason: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        Index("ix_resv_status_expiry", "status", "expires_at"),
        UniqueConstraint("order_id", "variant_id", name="uq_resv_order_variant"),
        CheckConstraint("quantity > 0", name="ck_resv_qty_pos"),
    )


class Cart(IdMixin, TimestampMixin, Base):
    __tablename__ = "carts"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", order_by="CartItem.id"
    )


class CartItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True, nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at_add: Mapped[Decimal] = mapped_column(Money, nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="items")
    variant = relationship("ProductVariant", lazy="joined")

    __table_args__ = (
        UniqueConstraint("cart_id", "variant_id", name="uq_cart_variant"),
        CheckConstraint("quantity > 0", name="ck_cart_qty_pos"),
    )


class Wishlist(IdMixin, TimestampMixin, Base):
    __tablename__ = "wishlists"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    items: Mapped[list["WishlistItem"]] = relationship(back_populates="wishlist", cascade="all, delete-orphan")


class WishlistItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "wishlist_items"
    wishlist_id: Mapped[int] = mapped_column(ForeignKey("wishlists.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id", ondelete="SET NULL"))

    wishlist: Mapped[Wishlist] = relationship(back_populates="items")
    product = relationship("Product", lazy="joined")

    __table_args__ = (UniqueConstraint("wishlist_id", "product_id", name="uq_wishlist_product"),)


class Coupon(IdMixin, TimestampMixin, Base):
    __tablename__ = "coupons"
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)  # percent | fixed | free_shipping
    value: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    min_cart_value: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    max_discount: Mapped[Decimal | None] = mapped_column(Money)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    usage_limit_total: Mapped[int | None] = mapped_column(Integer)
    usage_limit_per_user: Mapped[int | None] = mapped_column(Integer, default=1)
    times_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_order_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applies_to: Mapped[str] = mapped_column(String(20), default="all", nullable=False)  # all|categories|products
    category_ids: Mapped[list | None] = mapped_column(JSON)
    product_ids: Mapped[list | None] = mapped_column(JSON)
    customer_emails: Mapped[list | None] = mapped_column(JSON)  # restrict to these customers if set
    combinable_with_promotions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (CheckConstraint("value >= 0", name="ck_coupon_value_nonneg"),)


class CouponRedemption(IdMixin, Base):
    __tablename__ = "coupon_redemptions"
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"), index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="applied", nullable=False)  # applied | reversed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    coupon = relationship("Coupon", lazy="joined")

    __table_args__ = (UniqueConstraint("coupon_id", "order_id", name="uq_redemption_coupon_order"),)


class Promotion(IdMixin, TimestampMixin, Base):
    """Automatic promotions. Applied in ascending `priority`; a non-stackable promotion
    that applies stops further item-level promotions from being evaluated."""

    __tablename__ = "promotions"
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    badge_text: Mapped[str | None] = mapped_column(String(40))
    # percent_off | fixed_off | bogo | quantity_discount | free_shipping
    promo_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON)  # buy_qty, get_qty, min_qty, min_cart_value, max_discount
    applies_to: Mapped[str] = mapped_column(String(20), default="all", nullable=False)
    category_ids: Mapped[list | None] = mapped_column(JSON)
    product_ids: Mapped[list | None] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_stackable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
