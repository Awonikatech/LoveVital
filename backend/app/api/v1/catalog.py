from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db, utcnow
from app.core.deps import get_current_user
from app.core.errors import Conflict, NotFound
from app.core.money import D
from app.models import Category, Collection, Order, OrderItem, Product, ProductReview, ProductVariant, User
from app.services import catalog_service, shipping_service
from app.services.common import get_setting

router = APIRouter(tags=["catalog"])


def _csv(v: str | None) -> list[str] | None:
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


@router.get("/products", summary="List / search / filter products")
def list_products(
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=100, description="Search name, SKU, brand, category, keywords"),
    category: str | None = None,
    collection: str | None = None,
    product_type: Literal["jewellery", "apparel"] | None = None,
    brand: str | None = Query(None, description="Comma-separated"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    in_stock: bool = False,
    min_rating: float | None = Query(None, ge=0, le=5),
    min_discount: int | None = Query(None, ge=0, le=100),
    on_sale: bool = False,
    featured: bool = False,
    bestseller: bool = False,
    new_arrival: bool = False,
    color: str | None = None,
    size: str | None = None,
    material: str | None = None,
    plating: str | None = None,
    stone: str | None = None,
    style: str | None = None,
    fabric: str | None = None,
    fit: str | None = None,
    occasion: str | None = None,
    sort: Literal["popularity", "newest", "price_asc", "price_desc", "rating", "discount"] = "popularity",
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=60),
):
    params = {
        "q": q, "category": category, "collection": collection, "product_type": product_type, "brand": _csv(brand),
        "min_price": min_price, "max_price": max_price, "in_stock": in_stock, "min_rating": min_rating,
        "min_discount": min_discount, "on_sale": on_sale, "featured": featured, "bestseller": bestseller,
        "new_arrival": new_arrival, "color": _csv(color), "size": _csv(size), "material": _csv(material),
        "plating": _csv(plating), "stone": _csv(stone), "style": _csv(style), "fabric": _csv(fabric), "fit": _csv(fit),
        "occasion": _csv(occasion),
    }
    return catalog_service.list_products(db, params, page, page_size, sort)


@router.get("/products/{slug}", summary="Product details with variants, pricing and stock")
def product_detail(slug: str, db: Session = Depends(get_db)):
    p = db.scalar(
        select(Product).where(Product.slug == slug, Product.status == "active").options(
            selectinload(Product.images), selectinload(Product.variants).selectinload(ProductVariant.attribute_values),
            selectinload(Product.collections),
        )
    )
    if not p:
        raise NotFound("Product not found")
    promos = catalog_service.active_promotions(db)
    data = catalog_service.serialize_detail(db, p, promos)
    data["related"] = [catalog_service.serialize_card(r, promos) for r in catalog_service.related_products(db, p)]
    data["frequently_bought_together"] = [catalog_service.serialize_card(r, promos) for r in catalog_service.frequently_bought_together(db, p)]
    data["free_shipping_threshold"] = str(get_setting(db, "free_shipping_threshold", "999"))
    return data


@router.get("/products/{slug}/reviews")
def product_reviews(slug: str, db: Session = Depends(get_db), page: int = Query(1, ge=1), page_size: int = Query(10, le=50),
                    sort: Literal["recent", "highest", "lowest"] = "recent"):
    p = db.scalar(select(Product).where(Product.slug == slug))
    if not p:
        raise NotFound("Product not found")
    base = select(ProductReview).where(ProductReview.product_id == p.id, ProductReview.status == "published")
    order = {"recent": ProductReview.created_at.desc(), "highest": ProductReview.rating.desc(), "lowest": ProductReview.rating.asc()}[sort]
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    dist = dict(db.execute(select(ProductReview.rating, func.count()).where(ProductReview.product_id == p.id, ProductReview.status == "published").group_by(ProductReview.rating)).all())
    return {
        "items": [{"id": r.id, "rating": r.rating, "title": r.title, "body": r.body, "author": r.user.full_name.split(" ")[0] + (" " + r.user.full_name.split(" ")[-1][0] + "." if " " in r.user.full_name else ""),
                   "verified": r.is_verified_purchase, "created_at": r.created_at.isoformat()} for r in rows],
        "total": total, "page": page, "page_size": page_size,
        "average": float(p.rating_avg or 0), "count": p.rating_count,
        "distribution": {str(i): int(dist.get(i, 0)) for i in range(5, 0, -1)},
    }


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=150)
    body: str | None = Field(default=None, max_length=3000)


@router.post("/products/{slug}/reviews", status_code=201)
def create_review(slug: str, body: ReviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(Product).where(Product.slug == slug))
    if not p:
        raise NotFound("Product not found")
    bought = db.scalar(
        select(Order.id).join(OrderItem, OrderItem.order_id == Order.id)
        .where(Order.user_id == user.id, OrderItem.product_id == p.id, Order.status.in_(["delivered", "return_requested", "returned", "refunded", "refund_initiated"]))
        .limit(1)
    )
    existing = db.scalar(select(ProductReview).where(ProductReview.product_id == p.id, ProductReview.user_id == user.id))
    if existing:
        existing.rating, existing.title, existing.body = body.rating, body.title, body.body
        review = existing
    else:
        review = ProductReview(product_id=p.id, user_id=user.id, order_id=bought, rating=body.rating, title=body.title,
                               body=body.body, is_verified_purchase=bool(bought), status="published")
        db.add(review)
    db.flush()
    catalog_service.refresh_product_aggregates(db, p)
    db.commit()
    return {"id": review.id, "message": "Thanks for your review!"}


@router.get("/search/suggest", summary="Typeahead suggestions (synonym & typo tolerant)")
def suggest(q: str = Query(..., min_length=1, max_length=60), db: Session = Depends(get_db)):
    return catalog_service.suggestions(db, q)


def _cat_tree(c: Category) -> dict:
    return {"id": c.id, "name": c.name, "slug": c.slug, "image_url": c.image_url, "description": c.description,
            "display_order": c.display_order, "children": [_cat_tree(ch) for ch in c.children if ch.is_active]}


@router.get("/categories", summary="Category tree")
def categories(db: Session = Depends(get_db)):
    roots = db.scalars(select(Category).where(Category.parent_id.is_(None), Category.is_active.is_(True)).order_by(Category.display_order)).all()
    counts = dict(db.execute(select(Product.category_id, func.count()).where(Product.status == "active").group_by(Product.category_id)).all())
    def with_counts(node: dict) -> dict:
        node["product_count"] = counts.get(node["id"], 0) + sum(with_counts(ch)["product_count"] for ch in node["children"])
        return node
    return [with_counts(_cat_tree(r)) for r in roots]


@router.get("/collections")
def collections(db: Session = Depends(get_db), featured: bool = False):
    now = utcnow()
    stmt = select(Collection).where(Collection.is_active.is_(True)).order_by(Collection.display_order)
    if featured:
        stmt = stmt.where(Collection.is_featured.is_(True))
    rows = [c for c in db.scalars(stmt).all() if (not c.starts_at or c.starts_at <= now) and (not c.ends_at or c.ends_at > now)]
    return [{"id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url,
             "is_featured": c.is_featured, "product_count": len([p for p in c.products if p.status == "active"])} for c in rows]


@router.get("/delivery/estimate", summary="PIN-code serviceability and delivery estimate")
def delivery_estimate(pin: str = Query(..., min_length=6, max_length=6), product_slug: str | None = None,
                      order_value: float | None = None, db: Session = Depends(get_db)):
    processing = 1
    value = D(order_value) if order_value is not None else None
    if product_slug:
        p = db.scalar(select(Product).where(Product.slug == product_slug))
        if p:
            processing = p.processing_days
            value = value if value is not None else D(p.price_min)
    return shipping_service.estimate(db, pin, processing, value, D(get_setting(db, "free_shipping_threshold", "999")))
