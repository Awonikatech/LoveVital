from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, IdMixin, TimestampMixin

Money = Numeric(12, 2)


class TaxRate(IdMixin, TimestampMixin, Base):
    __tablename__ = "tax_rates"
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    hsn_code: Mapped[str | None] = mapped_column(String(10))
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # percent, prices are tax-inclusive
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Category(IdMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(200))
    seo_description: Mapped[str | None] = mapped_column(String(300))

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship(back_populates="parent", order_by="Category.display_order")


collection_products = Table(
    "collection_products",
    Base.metadata,
    Column("collection_id", Integer, ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("display_order", Integer, default=0, nullable=False),
)


class Collection(IdMixin, TimestampMixin, Base):
    __tablename__ = "collections"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)

    products: Mapped[list["Product"]] = relationship(secondary=collection_products, back_populates="collections")


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    brand: Mapped[str] = mapped_column(String(100), default="LoveVital", nullable=False, index=True)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # jewellery | apparel
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True, nullable=False)
    tax_rate_id: Mapped[int | None] = mapped_column(ForeignKey("tax_rates.id", ondelete="SET NULL"))
    short_description: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[dict | None] = mapped_column(JSON)
    care_instructions: Mapped[str | None] = mapped_column(Text)
    size_chart: Mapped[dict | None] = mapped_column(JSON)
    tags: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bestseller: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_new_arrival: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_days: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    min_order_qty: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    max_order_qty: Mapped[int] = mapped_column(SmallInteger, default=10, nullable=False)
    is_returnable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    return_window_days: Mapped[int] = mapped_column(SmallInteger, default=7, nullable=False)
    is_cod_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(200))
    seo_description: Mapped[str | None] = mapped_column(String(300))
    # Denormalised for fast listing/filter/sort; refreshed by catalog_service.refresh_product_aggregates
    price_min: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False, index=True)
    mrp_min: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    max_discount_pct: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False, index=True)
    rating_avg: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sold_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Lower-cased name/sku/brand/category/tags/attribute values; LIKE-searched (FULLTEXT-ready on MySQL).
    search_text: Mapped[str | None] = mapped_column(Text)

    category: Mapped[Category] = relationship(lazy="joined")
    tax_rate: Mapped[TaxRate | None] = relationship(lazy="joined")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.display_order"
    )
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductVariant.display_order"
    )
    collections: Mapped[list[Collection]] = relationship(secondary=collection_products, back_populates="products")

    __table_args__ = (
        Index("ix_products_status_type", "status", "product_type"),
        CheckConstraint("min_order_qty >= 1", name="ck_products_min_qty"),
        CheckConstraint("max_order_qty >= min_order_qty", name="ck_products_max_qty"),
    )


class ProductImage(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_images"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id", ondelete="SET NULL"), index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(200))
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    product: Mapped[Product] = relationship(back_populates="images")


class ProductAttribute(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_attributes"
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)  # color, size, material...
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    display_type: Mapped[str] = mapped_column(String(20), default="button", nullable=False)  # swatch|button|text
    is_variant_axis: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    values: Mapped[list["ProductAttributeValue"]] = relationship(
        back_populates="attribute", cascade="all, delete-orphan", order_by="ProductAttributeValue.display_order"
    )


class ProductAttributeValue(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_attribute_values"
    attribute_id: Mapped[int] = mapped_column(ForeignKey("product_attributes.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(90), nullable=False)
    swatch_hex: Mapped[str | None] = mapped_column(String(7))
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    attribute: Mapped[ProductAttribute] = relationship(back_populates="values", lazy="joined")

    __table_args__ = (UniqueConstraint("attribute_id", "slug", name="uq_attr_value_slug"),)


variant_attribute_values = Table(
    "variant_attribute_values",
    Base.metadata,
    Column("variant_id", Integer, ForeignKey("product_variants.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "attribute_value_id", Integer, ForeignKey("product_attribute_values.id", ondelete="CASCADE"), primary_key=True
    ),
    Index("ix_vav_value", "attribute_value_id"),
)


class ProductVariant(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_variants"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    mrp: Mapped[Decimal] = mapped_column(Money, nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_price: Mapped[Decimal | None] = mapped_column(Money)  # admin-only
    scheduled_sale_price: Mapped[Decimal | None] = mapped_column(Money)
    sale_starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    sale_ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    weight_grams: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped[Product] = relationship(back_populates="variants")
    attribute_values: Mapped[list[ProductAttributeValue]] = relationship(
        secondary=variant_attribute_values, lazy="selectin"
    )
    inventory: Mapped["Inventory | None"] = relationship(  # noqa: F821
        "Inventory", uselist=False, back_populates="variant", lazy="joined", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("mrp > 0", name="ck_variant_mrp_pos"),
        CheckConstraint("sale_price > 0 AND sale_price <= mrp", name="ck_variant_sale_le_mrp"),
    )


class ProductReview(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_reviews"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(150))
    body: Mapped[str | None] = mapped_column(Text)
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="published", nullable=False, index=True)

    user = relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint("product_id", "user_id", name="uq_review_product_user"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
    )
