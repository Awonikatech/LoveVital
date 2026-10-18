import csv
import io
import math
import os
import secrets
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db, utcnow
from app.core.deps import request_ip, require_permission
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.money import discount_pct, q
from app.models import (
    Category,
    Collection,
    Inventory,
    OrderItem,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductImage,
    ProductVariant,
    TaxRate,
    User,
)
from app.services import catalog_service, inventory_service
from app.services.common import audit, slugify

router = APIRouter(tags=["admin: products"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


class VariantIn(BaseModel):
    id: int | None = None
    sku: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9\-_]+$")
    name: str = Field(min_length=1, max_length=150)
    mrp: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    sale_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    scheduled_sale_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    sale_starts_at: datetime | None = None
    sale_ends_at: datetime | None = None
    weight_grams: Decimal | None = Field(default=None, ge=0)
    is_active: bool = True
    is_default: bool = False
    attribute_value_ids: list[int] = []
    stock: int | None = Field(default=None, ge=0, description="Initial stock for new variants")
    low_stock_threshold: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _prices(self):
        if self.sale_price > self.mrp:
            raise ValueError(f"{self.sku}: sale price cannot exceed MRP")
        if self.scheduled_sale_price is not None:
            if self.scheduled_sale_price > self.mrp:
                raise ValueError(f"{self.sku}: scheduled price cannot exceed MRP")
            if not self.sale_starts_at:
                raise ValueError(f"{self.sku}: scheduled price needs a start date")
            if self.sale_ends_at and self.sale_ends_at <= self.sale_starts_at:
                raise ValueError(f"{self.sku}: sale end must be after start")
        return self


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str | None = Field(default=None, max_length=220)
    sku: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9\-_]+$")
    brand: str = Field(default="LoveVital", max_length=100)
    product_type: Literal["jewellery", "apparel"]
    category_id: int
    tax_rate_id: int | None = None
    short_description: str | None = Field(default=None, max_length=300)
    description: str | None = None
    specifications: dict[str, str] | None = None
    care_instructions: str | None = None
    size_chart: dict | None = None
    tags: list[str] | None = None
    status: Literal["draft", "active", "archived"] = "draft"
    is_featured: bool = False
    is_bestseller: bool = False
    is_new_arrival: bool = False
    processing_days: int = Field(default=1, ge=0, le=30)
    min_order_qty: int = Field(default=1, ge=1, le=100)
    max_order_qty: int = Field(default=10, ge=1, le=100)
    is_returnable: bool = True
    return_window_days: int = Field(default=7, ge=0, le=60)
    is_cod_available: bool = True
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = Field(default=None, max_length=300)
    collection_ids: list[int] = []
    variants: list[VariantIn] = Field(min_length=1)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v):
        return slugify(v) if v else v

    @model_validator(mode="after")
    def _check(self):
        if self.max_order_qty < self.min_order_qty:
            raise ValueError("Max order quantity must be ≥ min order quantity")
        skus = [v.sku.upper() for v in self.variants]
        if len(skus) != len(set(skus)):
            raise ValueError("Variant SKUs must be unique")
        return self


def _admin_product(db: Session, p: Product, show_cost: bool) -> dict:
    out = {
        "id": p.id, "name": p.name, "slug": p.slug, "sku": p.sku, "brand": p.brand, "product_type": p.product_type,
        "category_id": p.category_id, "category_name": p.category.name, "tax_rate_id": p.tax_rate_id,
        "short_description": p.short_description, "description": p.description, "specifications": p.specifications or {},
        "care_instructions": p.care_instructions, "size_chart": p.size_chart, "tags": p.tags or [], "status": p.status,
        "is_featured": p.is_featured, "is_bestseller": p.is_bestseller, "is_new_arrival": p.is_new_arrival,
        "processing_days": p.processing_days, "min_order_qty": p.min_order_qty, "max_order_qty": p.max_order_qty,
        "is_returnable": p.is_returnable, "return_window_days": p.return_window_days, "is_cod_available": p.is_cod_available,
        "seo_title": p.seo_title, "seo_description": p.seo_description, "price_min": f"{p.price_min:.2f}", "mrp_min": f"{p.mrp_min:.2f}",
        "max_discount_pct": p.max_discount_pct, "rating_avg": float(p.rating_avg or 0), "rating_count": p.rating_count,
        "sold_count": p.sold_count, "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat(),
        "collection_ids": [c.id for c in p.collections],
        "images": [{"id": i.id, "url": i.url, "alt_text": i.alt_text, "is_primary": i.is_primary, "display_order": i.display_order,
                    "variant_id": i.variant_id} for i in sorted(p.images, key=lambda i: (not i.is_primary, i.display_order))],
        "variants": [],
        "total_stock": 0,
    }
    for v in p.variants:
        inv = v.inventory
        vd = {
            "id": v.id, "sku": v.sku, "name": v.name, "mrp": f"{v.mrp:.2f}", "sale_price": f"{v.sale_price:.2f}",
            "effective_price": f"{catalog_service.variant_price(v):.2f}", "discount_pct": discount_pct(v.mrp, v.sale_price),
            "scheduled_sale_price": f"{v.scheduled_sale_price:.2f}" if v.scheduled_sale_price is not None else None,
            "sale_starts_at": v.sale_starts_at.isoformat() if v.sale_starts_at else None,
            "sale_ends_at": v.sale_ends_at.isoformat() if v.sale_ends_at else None,
            "weight_grams": str(v.weight_grams) if v.weight_grams is not None else None, "is_active": v.is_active, "is_default": v.is_default,
            "attribute_value_ids": [av.id for av in v.attribute_values],
            "attributes": {av.attribute.code: av.value for av in v.attribute_values},
            "on_hand": inv.quantity_on_hand if inv else 0, "reserved": inv.quantity_reserved if inv else 0,
            "available": inv.available if inv else 0, "low_stock_threshold": inv.low_stock_threshold if inv else 5,
        }
        if show_cost:
            vd["cost_price"] = f"{v.cost_price:.2f}" if v.cost_price is not None else None
            vd["margin_pct"] = round(float((v.sale_price - v.cost_price) / v.sale_price * 100), 1) if v.cost_price else None
        out["variants"].append(vd)
        out["total_stock"] += vd["available"]
    return out


def _load(db: Session, product_id: int) -> Product:
    p = db.scalar(select(Product).where(Product.id == product_id).options(
        selectinload(Product.images), selectinload(Product.variants).selectinload(ProductVariant.attribute_values), selectinload(Product.collections)))
    if not p:
        raise NotFound("Product not found")
    return p


@router.get("/products")
def list_products(user: User = Depends(require_permission("products:read")), db: Session = Depends(get_db),
                  q_: str | None = Query(None, alias="q"), status: str | None = None, category_id: int | None = None,
                  product_type: str | None = None, stock: Literal["low", "out", "in"] | None = None, flag: Literal["featured", "bestseller", "new"] | None = None,
                  sort: Literal["newest", "name", "price_asc", "price_desc", "stock", "sold"] = "newest",
                  page: int = Query(1, ge=1), page_size: int = Query(20, le=100)):
    stmt = select(Product).options(selectinload(Product.images), selectinload(Product.variants).selectinload(ProductVariant.attribute_values))
    if q_:
        like = f"%{q_.lower()}%"
        stmt = stmt.where(or_(func.lower(Product.name).like(like), func.lower(Product.sku).like(like), func.lower(Product.search_text).like(like)))
    if status:
        stmt = stmt.where(Product.status == status)
    if category_id:
        cat = db.get(Category, category_id)
        if cat:
            stmt = stmt.where(Product.category_id.in_(catalog_service.category_descendant_ids(db, cat)))
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if flag:
        stmt = stmt.where({"featured": Product.is_featured, "bestseller": Product.is_bestseller, "new": Product.is_new_arrival}[flag].is_(True))
    avail = (select(func.coalesce(func.sum(Inventory.quantity_on_hand - Inventory.quantity_reserved), 0))
             .join(ProductVariant, ProductVariant.id == Inventory.variant_id)
             .where(ProductVariant.product_id == Product.id, ProductVariant.is_active.is_(True)).correlate(Product).scalar_subquery())
    if stock == "out":
        stmt = stmt.where(avail <= 0)
    elif stock == "low":
        stmt = stmt.where(avail > 0, avail <= 10)
    elif stock == "in":
        stmt = stmt.where(avail > 0)
    order = {"newest": Product.id.desc(), "name": Product.name.asc(), "price_asc": Product.price_min.asc(),
             "price_desc": Product.price_min.desc(), "stock": avail.asc(), "sold": Product.sold_count.desc()}[sort]
    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(Product.id).subquery()))
    rows = db.scalars(stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)).unique().all()
    show_cost = user.has_permission("products:cost")
    items = []
    for p in rows:
        d = _admin_product(db, p, show_cost)
        items.append({k: d[k] for k in ("id", "name", "slug", "sku", "brand", "product_type", "category_name", "status", "is_featured",
                                         "is_bestseller", "is_new_arrival", "price_min", "mrp_min", "max_discount_pct", "total_stock",
                                         "sold_count", "rating_avg", "updated_at")} | {"image": d["images"][0]["url"] if d["images"] else None,
                                                                                      "variant_count": len(d["variants"])})
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": math.ceil(total / page_size) if total else 0}


@router.get("/products/meta")
def product_meta(user: User = Depends(require_permission("products:read")), db: Session = Depends(get_db)):
    cats = db.scalars(select(Category).order_by(Category.parent_id.is_not(None), Category.display_order)).all()
    attrs = db.scalars(select(ProductAttribute).options(selectinload(ProductAttribute.values)).order_by(ProductAttribute.display_order)).all()
    return {
        "categories": [{"id": c.id, "name": c.name, "slug": c.slug, "parent_id": c.parent_id,
                        "label": f"{c.parent.name} › {c.name}" if c.parent else c.name} for c in cats],
        "tax_rates": [{"id": t.id, "name": t.name, "rate": f"{t.rate:.2f}", "hsn_code": t.hsn_code} for t in db.scalars(select(TaxRate)).all()],
        "collections": [{"id": c.id, "name": c.name} for c in db.scalars(select(Collection).order_by(Collection.display_order)).all()],
        "attributes": [{"id": a.id, "code": a.code, "name": a.name, "is_variant_axis": a.is_variant_axis,
                        "values": [{"id": v.id, "value": v.value, "slug": v.slug, "hex": v.swatch_hex} for v in a.values]} for a in attrs],
        "can_view_cost": user.has_permission("products:cost"),
    }


@router.get("/products/{product_id}")
def get_product(product_id: int, user: User = Depends(require_permission("products:read")), db: Session = Depends(get_db)):
    return _admin_product(db, _load(db, product_id), user.has_permission("products:cost"))


def _apply(db: Session, p: Product, body: ProductIn, user: User, creating: bool) -> None:
    if not db.get(Category, body.category_id):
        raise ValidationFailed("Category not found")
    slug = body.slug or slugify(body.name)
    clash = db.scalar(select(Product.id).where(Product.slug == slug, Product.id != (p.id or 0)))
    if clash:
        slug = f"{slug}-{secrets.token_hex(2)}"
    if db.scalar(select(Product.id).where(func.upper(Product.sku) == body.sku.upper(), Product.id != (p.id or 0))):
        raise Conflict(f"Product SKU {body.sku} already exists", code="duplicate_sku")
    fields = body.model_dump(exclude={"variants", "collection_ids", "slug"})
    for k, v in fields.items():
        setattr(p, k, v)
    p.sku = body.sku.upper()
    p.slug = slug
    if body.status == "active" and not p.published_at:
        p.published_at = utcnow()
    if body.status == "archived":
        p.archived_at = p.archived_at or utcnow()
    p.collections = list(db.scalars(select(Collection).where(Collection.id.in_(body.collection_ids))).all()) if body.collection_ids else []
    existing = {v.id: v for v in p.variants}
    seen = set()
    show_cost = user.has_permission("products:cost")
    for i, vin in enumerate(body.variants):
        other = db.scalar(select(ProductVariant).where(func.upper(ProductVariant.sku) == vin.sku.upper()))
        if other and other.id != vin.id:
            raise Conflict(f"Variant SKU {vin.sku} already exists", code="duplicate_sku")
        v = existing.get(vin.id) if vin.id else None
        if vin.id and not v:
            raise ValidationFailed(f"Variant {vin.id} does not belong to this product")
        if v is None:
            v = ProductVariant(product=p)
            p.variants.append(v)
        v.sku, v.name, v.mrp, v.sale_price = vin.sku.upper(), vin.name, q(vin.mrp), q(vin.sale_price)
        if show_cost:
            v.cost_price = q(vin.cost_price) if vin.cost_price is not None else None
        v.scheduled_sale_price = q(vin.scheduled_sale_price) if vin.scheduled_sale_price is not None else None
        v.sale_starts_at, v.sale_ends_at, v.weight_grams = vin.sale_starts_at, vin.sale_ends_at, vin.weight_grams
        v.is_active, v.is_default, v.display_order = vin.is_active, vin.is_default, i
        v.attribute_values = list(db.scalars(select(ProductAttributeValue).where(ProductAttributeValue.id.in_(vin.attribute_value_ids))).all())
        db.flush()
        if v.inventory is None:
            v.inventory = Inventory(variant_id=v.id, quantity_on_hand=0, quantity_reserved=0, low_stock_threshold=vin.low_stock_threshold or 5)
            db.flush()
            if vin.stock:
                inventory_service.adjust(db, v.id, vin.stock, "initial", "Initial stock", user)
        elif vin.low_stock_threshold is not None:
            v.inventory.low_stock_threshold = vin.low_stock_threshold
        seen.add(v.id)
    for vid, v in existing.items():
        if vid not in seen:
            used = db.scalar(select(OrderItem.id).where(OrderItem.variant_id == vid).limit(1))
            if used or (v.inventory and v.inventory.quantity_reserved):
                v.is_active = False  # keep for order history
            else:
                p.variants.remove(v)
                db.delete(v)
    if not any(v.is_default for v in p.variants if v.is_active):
        first = next((v for v in p.variants if v.is_active), None)
        if first:
            first.is_default = True
    db.flush()
    db.refresh(p)
    catalog_service.refresh_product_aggregates(db, p)


@router.post("/products", status_code=201)
def create_product(body: ProductIn, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    # Check before the placeholder row is flushed, otherwise the UNIQUE constraint fires first (500 instead of 409).
    if db.scalar(select(Product.id).where(func.upper(Product.sku) == body.sku.upper())):
        raise Conflict(f"Product SKU {body.sku} already exists", code="duplicate_sku")
    p = Product(name=body.name, slug="tmp-" + secrets.token_hex(6), sku=body.sku.upper(), product_type=body.product_type,
                category_id=body.category_id)
    db.add(p)
    db.flush()
    _apply(db, p, body, user, True)
    audit(db, user, "product.create", "product", p.id, {"sku": p.sku, "name": p.name}, request_ip(request))
    db.commit()
    return _admin_product(db, _load(db, p.id), user.has_permission("products:cost"))


@router.put("/products/{product_id}")
def update_product(product_id: int, body: ProductIn, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    p = _load(db, product_id)
    before = {"status": p.status, "price_min": str(p.price_min), "name": p.name}
    _apply(db, p, body, user, False)
    audit(db, user, "product.update", "product", p.id, {"before": before, "after": {"status": p.status, "price_min": str(p.price_min), "name": p.name}}, request_ip(request))
    db.commit()
    return _admin_product(db, _load(db, p.id), user.has_permission("products:cost"))


class StatusIn(BaseModel):
    status: Literal["draft", "active", "archived"] | None = None
    is_featured: bool | None = None
    is_bestseller: bool | None = None
    is_new_arrival: bool | None = None


@router.patch("/products/{product_id}")
def patch_product(product_id: int, body: StatusIn, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    p = _load(db, product_id)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(p, k, v)
    if body.status == "active" and not p.published_at:
        p.published_at = utcnow()
    if body.status == "archived":
        p.archived_at = utcnow()
    audit(db, user, "product.patch", "product", p.id, changes, request_ip(request))
    db.commit()
    return {"id": p.id, **changes}


@router.delete("/products/{product_id}")
def delete_product(product_id: int, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    p = _load(db, product_id)
    used = db.scalar(select(OrderItem.id).where(OrderItem.product_id == p.id).limit(1))
    if used:
        p.status, p.archived_at = "archived", utcnow()
        audit(db, user, "product.archive", "product", p.id, {"reason": "referenced by orders"}, request_ip(request))
        db.commit()
        return {"archived": True, "message": "Product has order history, so it was archived instead of deleted."}
    audit(db, user, "product.delete", "product", p.id, {"sku": p.sku}, request_ip(request))
    db.delete(p)
    db.commit()
    return {"deleted": True}


# ------------------------------------------------------------------ images
ALLOWED_IMAGE = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png", b"RIFF": ".webp", b"GIF8": ".gif"}


def _sniff(head: bytes) -> str | None:
    for magic, ext in ALLOWED_IMAGE.items():
        if head.startswith(magic):
            if ext == ".webp" and head[8:12] != b"WEBP":
                return None
            return ext
    return None


async def save_upload(file: UploadFile, folder: str) -> str:
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise ValidationFailed("Only JPEG, PNG, WebP or GIF images are allowed", code="invalid_file_type")
    data = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationFailed(f"Image must be smaller than {settings.MAX_UPLOAD_MB} MB", code="file_too_large")
    ext = _sniff(data[:16])
    if not ext:
        raise ValidationFailed("File content is not a valid image", code="invalid_file_type")
    name = f"{secrets.token_hex(12)}{ext}"  # never trust the client filename
    path = os.path.join(BASE_DIR, settings.MEDIA_DIR, "uploads", folder)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, name), "wb") as fh:
        fh.write(data)
    return f"/media/uploads/{folder}/{name}"


@router.post("/products/{product_id}/images", status_code=201)
async def upload_image(product_id: int, request: Request, file: UploadFile = File(...), user: User = Depends(require_permission("products:write")),
                       db: Session = Depends(get_db)):
    p = _load(db, product_id)
    url = await save_upload(file, "products")
    img = ProductImage(product_id=p.id, url=url, alt_text=p.name, display_order=len(p.images), is_primary=not p.images)
    db.add(img)
    audit(db, user, "product.image.add", "product", p.id, {"url": url}, request_ip(request))
    db.commit()
    return {"id": img.id, "url": url, "is_primary": img.is_primary}


class ImageUrlIn(BaseModel):
    url: str = Field(pattern=r"^(https://|/static/|/media/)", max_length=500)
    alt_text: str | None = None


@router.post("/products/{product_id}/images/url", status_code=201)
def add_image_url(product_id: int, body: ImageUrlIn, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    p = _load(db, product_id)
    img = ProductImage(product_id=p.id, url=body.url, alt_text=body.alt_text or p.name, display_order=len(p.images), is_primary=not p.images)
    db.add(img)
    db.commit()
    return {"id": img.id, "url": img.url}


class ImagePatch(BaseModel):
    is_primary: bool | None = None
    display_order: int | None = None
    alt_text: str | None = None
    variant_id: int | None = None


@router.patch("/products/{product_id}/images/{image_id}")
def patch_image(product_id: int, image_id: int, body: ImagePatch, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    p = _load(db, product_id)
    img = next((i for i in p.images if i.id == image_id), None)
    if not img:
        raise NotFound("Image not found")
    if body.is_primary:
        for i in p.images:
            i.is_primary = i.id == image_id
    for k in ("display_order", "alt_text", "variant_id"):
        v = getattr(body, k)
        if v is not None:
            setattr(img, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/products/{product_id}/images/{image_id}")
def delete_image(product_id: int, image_id: int, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    p = _load(db, product_id)
    img = next((i for i in p.images if i.id == image_id), None)
    if not img:
        raise NotFound("Image not found")
    was_primary = img.is_primary
    p.images.remove(img)
    db.delete(img)
    if was_primary and p.images:
        p.images[0].is_primary = True
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ CSV
CSV_FIELDS = ["product_sku", "product_name", "slug", "product_type", "category_slug", "brand", "status", "short_description", "tags",
              "variant_sku", "variant_name", "mrp", "sale_price", "cost_price", "stock", "attributes", "image_url"]


@router.get("/products-export.csv")
def export_csv(user: User = Depends(require_permission("products:read")), db: Session = Depends(get_db)):
    show_cost = user.has_permission("products:cost")
    rows = db.scalars(select(Product).options(selectinload(Product.images), selectinload(Product.variants)).order_by(Product.id)).unique().all()
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    w.writeheader()
    for p in rows:
        for v in p.variants:
            w.writerow({
                "product_sku": p.sku, "product_name": p.name, "slug": p.slug, "product_type": p.product_type, "category_slug": p.category.slug,
                "brand": p.brand, "status": p.status, "short_description": p.short_description or "", "tags": "|".join(p.tags or []),
                "variant_sku": v.sku, "variant_name": v.name, "mrp": f"{v.mrp:.2f}", "sale_price": f"{v.sale_price:.2f}",
                "cost_price": f"{v.cost_price:.2f}" if (show_cost and v.cost_price is not None) else "",
                "stock": v.inventory.quantity_on_hand if v.inventory else 0,
                "attributes": ";".join(f"{av.attribute.code}={av.value}" for av in v.attribute_values),
                "image_url": p.images[0].url if p.images else "",
            })
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="products-{utcnow():%Y%m%d}.csv"'})


@router.post("/products-import")
async def import_csv(request: Request, file: UploadFile = File(...), dry_run: bool = False,
                     user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValidationFailed("CSV must be under 5 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationFailed("CSV must be UTF-8 encoded")
    reader = csv.DictReader(io.StringIO(text))
    missing = {"product_sku", "product_name", "product_type", "category_slug", "variant_sku", "mrp", "sale_price"} - set(reader.fieldnames or [])
    if missing:
        raise ValidationFailed(f"Missing columns: {', '.join(sorted(missing))}")
    created = updated = 0
    errors: list[dict] = []
    attr_cache = {(a.attribute.code, a.value.lower()): a for a in db.scalars(select(ProductAttributeValue)).all()}
    for lineno, row in enumerate(reader, start=2):
        try:
            with db.begin_nested():
                cat = db.scalar(select(Category).where(Category.slug == row["category_slug"].strip()))
                if not cat:
                    raise ValueError(f"unknown category '{row['category_slug']}'")
                mrp, sale = q(row["mrp"]), q(row["sale_price"])
                if sale > mrp or sale <= 0:
                    raise ValueError("sale_price must be > 0 and ≤ mrp")
                p = db.scalar(select(Product).where(func.upper(Product.sku) == row["product_sku"].strip().upper()))
                if not p:
                    p = Product(sku=row["product_sku"].strip().upper(), name=row["product_name"].strip(),
                                slug=row.get("slug") or f"{slugify(row['product_name'])}-{secrets.token_hex(2)}",
                                product_type=row["product_type"].strip(), category_id=cat.id, status=row.get("status") or "draft",
                                brand=row.get("brand") or "LoveVital")
                    db.add(p)
                    db.flush()
                    created += 1
                else:
                    updated += 1
                p.name, p.category_id = row["product_name"].strip(), cat.id
                if row.get("short_description"):
                    p.short_description = row["short_description"][:300]
                if row.get("tags"):
                    p.tags = [t for t in row["tags"].split("|") if t]
                if row.get("status") in ("draft", "active", "archived"):
                    p.status = row["status"]
                    if p.status == "active" and not p.published_at:
                        p.published_at = utcnow()
                v = db.scalar(select(ProductVariant).where(func.upper(ProductVariant.sku) == row["variant_sku"].strip().upper()))
                if v and v.product_id != p.id:
                    raise ValueError(f"variant SKU {row['variant_sku']} belongs to another product")
                if not v:
                    v = ProductVariant(product_id=p.id, sku=row["variant_sku"].strip().upper(), name=row.get("variant_name") or "Default",
                                       mrp=mrp, sale_price=sale, is_default=not p.variants)
                    db.add(v)
                    db.flush()
                    db.add(Inventory(variant_id=v.id, quantity_on_hand=0, quantity_reserved=0))
                    db.flush()
                v.mrp, v.sale_price = mrp, sale
                v.name = row.get("variant_name") or v.name
                if row.get("cost_price") and user.has_permission("products:cost"):
                    v.cost_price = q(row["cost_price"])
                if row.get("attributes"):
                    vals = []
                    for pair in row["attributes"].split(";"):
                        if "=" in pair:
                            code, val = pair.split("=", 1)
                            av = attr_cache.get((code.strip(), val.strip().lower()))
                            if av:
                                vals.append(av)
                    v.attribute_values = vals
                if row.get("stock", "").strip():
                    target = int(row["stock"])
                    inv = db.scalar(select(Inventory).where(Inventory.variant_id == v.id))
                    delta = target - (inv.quantity_on_hand if inv else 0)
                    if delta:
                        inventory_service.adjust(db, v.id, delta, "adjustment", "CSV import", user)
                if row.get("image_url") and not p.images and row["image_url"].startswith(("https://", "/static/", "/media/")):
                    db.add(ProductImage(product_id=p.id, url=row["image_url"], alt_text=p.name, is_primary=True))
                db.flush()
                db.refresh(p)
                catalog_service.refresh_product_aggregates(db, p)
                if dry_run:
                    raise _DryRun()
        except _DryRun:
            pass
        except Exception as e:  # collect row errors, keep going
            errors.append({"line": lineno, "error": str(e)[:200]})
    if dry_run:
        db.rollback()
    else:
        audit(db, user, "product.import", "product", None, {"created": created, "updated": updated, "errors": len(errors)}, request_ip(request))
        db.commit()
    return {"created": created, "updated": updated, "errors": errors, "dry_run": dry_run}


class _DryRun(Exception):
    pass
