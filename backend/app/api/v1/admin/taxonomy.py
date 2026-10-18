"""Categories, collections, attributes and tax rates."""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import request_ip, require_permission
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import Category, Collection, Product, ProductAttribute, ProductAttributeValue, TaxRate, User
from app.services.common import audit, slugify

router = APIRouter(tags=["admin: catalog"])


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str | None = None
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    display_order: int = 0
    is_active: bool = True
    seo_title: str | None = None
    seo_description: str | None = None


def _cat(c: Category, counts: dict) -> dict:
    return {"id": c.id, "name": c.name, "slug": c.slug, "parent_id": c.parent_id, "parent_name": c.parent.name if c.parent else None,
            "description": c.description, "image_url": c.image_url, "display_order": c.display_order, "is_active": c.is_active,
            "seo_title": c.seo_title, "seo_description": c.seo_description, "product_count": counts.get(c.id, 0)}


@router.get("/categories")
def list_categories(user: User = Depends(require_permission("products:read")), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Product.category_id, func.count()).group_by(Product.category_id)).all())
    rows = db.scalars(select(Category).order_by(Category.parent_id.is_not(None), Category.parent_id, Category.display_order, Category.name)).all()
    return [_cat(c, counts) for c in rows]


def _save_cat(db: Session, c: Category, body: CategoryIn) -> None:
    slug = slugify(body.slug or body.name)
    if db.scalar(select(Category.id).where(Category.slug == slug, Category.id != (c.id or 0))):
        raise Conflict(f"Slug '{slug}' is already used", code="duplicate_slug")
    if body.parent_id:
        if body.parent_id == c.id:
            raise ValidationFailed("A category cannot be its own parent")
        parent = db.get(Category, body.parent_id)
        if not parent:
            raise ValidationFailed("Parent category not found")
        anc = parent
        while anc is not None:
            if anc.id == c.id:
                raise ValidationFailed("That would create a loop in the category tree")
            anc = anc.parent
    for k, v in body.model_dump(exclude={"slug"}).items():
        setattr(c, k, v)
    c.slug = slug


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    c = Category(name=body.name, slug="tmp")
    _save_cat(db, c, body)
    db.add(c)
    db.flush()
    audit(db, user, "category.create", "category", c.id, {"name": c.name}, request_ip(request))
    db.commit()
    return _cat(c, {})


@router.put("/categories/{cid}")
def update_category(cid: int, body: CategoryIn, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    c = db.get(Category, cid)
    if not c:
        raise NotFound("Category not found")
    _save_cat(db, c, body)
    audit(db, user, "category.update", "category", c.id, body.model_dump(), request_ip(request))
    db.commit()
    return _cat(c, {})


@router.delete("/categories/{cid}")
def delete_category(cid: int, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    c = db.get(Category, cid)
    if not c:
        raise NotFound("Category not found")
    if db.scalar(select(Product.id).where(Product.category_id == cid).limit(1)):
        raise Conflict("Move or delete this category's products first", code="category_in_use")
    if c.children:
        raise Conflict("Delete or move the sub-categories first", code="category_has_children")
    audit(db, user, "category.delete", "category", cid, {"name": c.name}, request_ip(request))
    db.delete(c)
    db.commit()
    return {"deleted": True}


@router.post("/uploads/image", status_code=201)
async def upload_generic_image(file: UploadFile = File(...), folder: str = "content", user: User = Depends(require_permission("content:write"))):
    from app.api.v1.admin.products import save_upload

    if folder not in ("content", "categories", "collections", "banners"):
        raise ValidationFailed("Invalid folder")
    return {"url": await save_upload(file, folder)}


class CollectionIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    is_featured: bool = False
    is_active: bool = True
    display_order: int = 0
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    product_ids: list[int] = []


def _col(c: Collection) -> dict:
    return {"id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url, "is_featured": c.is_featured,
            "is_active": c.is_active, "display_order": c.display_order, "starts_at": c.starts_at.isoformat() if c.starts_at else None,
            "ends_at": c.ends_at.isoformat() if c.ends_at else None, "product_ids": [p.id for p in c.products],
            "products": [{"id": p.id, "name": p.name, "sku": p.sku} for p in c.products]}


@router.get("/collections")
def list_collections(user: User = Depends(require_permission("products:read")), db: Session = Depends(get_db)):
    return [_col(c) for c in db.scalars(select(Collection).options(selectinload(Collection.products)).order_by(Collection.display_order)).all()]


def _save_col(db: Session, c: Collection, body: CollectionIn) -> None:
    slug = slugify(body.slug or body.name)
    if db.scalar(select(Collection.id).where(Collection.slug == slug, Collection.id != (c.id or 0))):
        raise Conflict(f"Slug '{slug}' is already used", code="duplicate_slug")
    for k, v in body.model_dump(exclude={"slug", "product_ids"}).items():
        setattr(c, k, v)
    c.slug = slug
    c.products = list(db.scalars(select(Product).where(Product.id.in_(body.product_ids))).all()) if body.product_ids else []


@router.post("/collections", status_code=201)
def create_collection(body: CollectionIn, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    c = Collection(name=body.name, slug="tmp")
    _save_col(db, c, body)
    db.add(c)
    db.flush()
    audit(db, user, "collection.create", "collection", c.id, {"name": c.name}, request_ip(request))
    db.commit()
    return _col(c)


@router.put("/collections/{cid}")
def update_collection(cid: int, body: CollectionIn, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    c = db.get(Collection, cid)
    if not c:
        raise NotFound("Collection not found")
    _save_col(db, c, body)
    audit(db, user, "collection.update", "collection", c.id, {"name": c.name, "products": len(body.product_ids)}, request_ip(request))
    db.commit()
    return _col(c)


@router.delete("/collections/{cid}")
def delete_collection(cid: int, request: Request, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    c = db.get(Collection, cid)
    if not c:
        raise NotFound("Collection not found")
    audit(db, user, "collection.delete", "collection", cid, {"name": c.name}, request_ip(request))
    db.delete(c)
    db.commit()
    return {"deleted": True}


class AttrValueIn(BaseModel):
    value: str = Field(min_length=1, max_length=80)
    swatch_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


@router.get("/attributes")
def list_attributes(user: User = Depends(require_permission("products:read")), db: Session = Depends(get_db)):
    attrs = db.scalars(select(ProductAttribute).options(selectinload(ProductAttribute.values)).order_by(ProductAttribute.display_order)).all()
    return [{"id": a.id, "code": a.code, "name": a.name, "is_variant_axis": a.is_variant_axis, "is_filterable": a.is_filterable,
             "values": [{"id": v.id, "value": v.value, "slug": v.slug, "hex": v.swatch_hex} for v in a.values]} for a in attrs]


@router.post("/attributes/{aid}/values", status_code=201)
def add_attribute_value(aid: int, body: AttrValueIn, user: User = Depends(require_permission("products:write")), db: Session = Depends(get_db)):
    a = db.get(ProductAttribute, aid)
    if not a:
        raise NotFound("Attribute not found")
    slug = slugify(body.value)
    if db.scalar(select(ProductAttributeValue.id).where(ProductAttributeValue.attribute_id == aid, ProductAttributeValue.slug == slug)):
        raise Conflict("That value already exists")
    v = ProductAttributeValue(attribute_id=aid, value=body.value, slug=slug, swatch_hex=body.swatch_hex, display_order=len(a.values))
    db.add(v)
    db.commit()
    return {"id": v.id, "value": v.value, "slug": v.slug, "hex": v.swatch_hex}


class TaxIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    hsn_code: str | None = Field(default=None, max_length=10)
    rate: Decimal = Field(ge=0, le=40)
    is_active: bool = True


@router.get("/tax-rates")
def list_tax(user: User = Depends(require_permission("products:read")), db: Session = Depends(get_db)):
    return [{"id": t.id, "name": t.name, "hsn_code": t.hsn_code, "rate": f"{t.rate:.2f}", "is_active": t.is_active} for t in db.scalars(select(TaxRate)).all()]


@router.post("/tax-rates", status_code=201)
def create_tax(body: TaxIn, request: Request, user: User = Depends(require_permission("settings:write")), db: Session = Depends(get_db)):
    t = TaxRate(**body.model_dump())
    db.add(t)
    db.flush()
    audit(db, user, "tax_rate.create", "tax_rate", t.id, body.model_dump(), request_ip(request))
    db.commit()
    return {"id": t.id}


@router.put("/tax-rates/{tid}")
def update_tax(tid: int, body: TaxIn, request: Request, user: User = Depends(require_permission("settings:write")), db: Session = Depends(get_db)):
    t = db.get(TaxRate, tid)
    if not t:
        raise NotFound("Tax rate not found")
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    audit(db, user, "tax_rate.update", "tax_rate", t.id, body.model_dump(), request_ip(request))
    db.commit()
    return {"id": t.id}
