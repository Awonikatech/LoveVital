"""Catalog queries, product serialisation, search and denormalised aggregates."""
from __future__ import annotations

import difflib
import math
import re
from decimal import Decimal

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import utcnow
from app.core.money import D, discount_pct, q
from app.models import (
    Category,
    Collection,
    Inventory,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductReview,
    ProductVariant,
    Promotion,
    collection_products,
    variant_attribute_values,
)
from app.services.pricing import effective_unit_price

SYNONYMS: dict[str, list[str]] = {
    "jhumka": ["jhumka", "jhumki", "earring"],
    "jhumki": ["jhumka", "jhumki", "earring"],
    "earring": ["earring", "jhumka", "stud", "hoop", "chandbali"],
    "earrings": ["earring", "jhumka", "stud", "hoop", "chandbali"],
    "necklace": ["necklace", "haar", "choker", "pendant", "mala"],
    "haar": ["haar", "necklace"],
    "bangle": ["bangle", "kada", "chudi", "kangan"],
    "bangles": ["bangle", "kada", "chudi", "kangan"],
    "kada": ["kada", "bangle"],
    "kurti": ["kurti", "kurta"],
    "kurta": ["kurta", "kurti"],
    "sari": ["saree", "sari"],
    "saree": ["saree", "sari"],
    "lehenga": ["lehenga", "lehnga", "ghagra"],
    "ring": ["ring", "angoothi"],
    "bracelet": ["bracelet", "cuff", "kada"],
    "top": ["top", "blouse", "shirt"],
    "pants": ["trouser", "pant", "palazzo"],
    "trousers": ["trouser", "pant", "palazzo"],
    "silver": ["silver", "oxidised", "oxidized"],
    "oxidized": ["oxidised", "oxidized", "silver"],
    "gold": ["gold"],
    "anklet": ["anklet", "payal"],
    "payal": ["payal", "anklet"],
}


def _stem(token: str) -> str:
    if len(token) > 3 and token.endswith("es") and not token.endswith("ses"):
        return token[:-2] if token[:-2].endswith(("ch", "sh", "x")) else token[:-1]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def expand_query(q_text: str) -> list[list[str]]:
    groups = []
    for raw in re.findall(r"[a-z0-9\-]+", q_text.lower()):
        if len(raw) < 2:
            continue
        variants = set(SYNONYMS.get(raw, [])) | set(SYNONYMS.get(_stem(raw), [])) | {_stem(raw)}
        groups.append(sorted(variants))
    return groups


def category_descendant_ids(db: Session, root: Category) -> list[int]:
    ids, frontier = [root.id], [root.id]
    while frontier:
        children = db.scalars(select(Category.id).where(Category.parent_id.in_(frontier))).all()
        frontier = [c for c in children if c not in ids]
        ids += frontier
    return ids


def category_ancestor_ids(category: Category | None) -> list[int]:
    out = []
    while category is not None:
        out.append(category.id)
        category = category.parent
    return out


def variant_price(v: ProductVariant) -> Decimal:
    return effective_unit_price(v.sale_price, v.scheduled_sale_price, v.sale_starts_at, v.sale_ends_at, utcnow())


def stock_status(available: int, threshold: int = 5) -> str:
    if available <= 0:
        return "out_of_stock"
    if available <= threshold:
        return "low_stock"
    return "in_stock"


def refresh_product_aggregates(db: Session, product: Product) -> None:
    active = [v for v in product.variants if v.is_active]
    if active:
        prices = [(variant_price(v), q(v.mrp)) for v in active]
        cheapest = min(prices, key=lambda p: p[0])
        product.price_min, product.mrp_min = cheapest
        product.max_discount_pct = max(discount_pct(m, p) for p, m in prices)
    stats = db.execute(
        select(func.count(ProductReview.id), func.avg(ProductReview.rating)).where(
            ProductReview.product_id == product.id, ProductReview.status == "published"
        )
    ).one() if product.id else (0, None)
    product.rating_count = int(stats[0] or 0)
    product.rating_avg = q(stats[1] or 0)
    parts = [product.name, product.sku, product.brand, product.product_type, product.short_description or ""]
    if product.category:
        parts.append(product.category.name)
        if product.category.parent:
            parts.append(product.category.parent.name)
    parts += list(product.tags or [])
    for v in product.variants:
        parts.append(v.sku)
        parts += [av.value for av in v.attribute_values]
    product.search_text = " ".join(dict.fromkeys(p.lower() for p in parts if p))[:4000]


def active_promotions(db: Session) -> list[Promotion]:
    now = utcnow()
    return list(
        db.scalars(
            select(Promotion).where(
                Promotion.is_active.is_(True),
                or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
                or_(Promotion.ends_at.is_(None), Promotion.ends_at > now),
            ).order_by(Promotion.priority)
        )
    )


def promo_badges_for(product: Product, promos: list[Promotion]) -> list[str]:
    cat_ids = set(category_ancestor_ids(product.category))
    out = []
    for p in promos:
        if not p.badge_text:
            continue
        if p.applies_to == "all" or (p.applies_to == "categories" and cat_ids & set(p.category_ids or [])) or (
            p.applies_to == "products" and product.id in (p.product_ids or [])
        ):
            out.append(p.badge_text)
    return out[:2]


def _primary_images(product: Product) -> tuple[str | None, str | None]:
    imgs = sorted(product.images, key=lambda i: (not i.is_primary, i.display_order))
    first = imgs[0].url if imgs else None
    second = imgs[1].url if len(imgs) > 1 else None
    return first, second


def serialize_card(product: Product, promos: list[Promotion] | None = None) -> dict:
    active = [v for v in product.variants if v.is_active]
    total_avail = sum(v.inventory.available if v.inventory else 0 for v in active)
    threshold = min((v.inventory.low_stock_threshold for v in active if v.inventory), default=5)
    default = next((v for v in active if v.is_default), active[0] if active else None)
    img, hover = _primary_images(product)
    colors = []
    seen = set()
    for v in active:
        for av in v.attribute_values:
            if av.attribute.code == "color" and av.slug not in seen:
                seen.add(av.slug)
                colors.append({"value": av.value, "slug": av.slug, "hex": av.swatch_hex})
    price = q(product.price_min)
    mrp = q(product.mrp_min)
    return {
        "id": product.id,
        "slug": product.slug,
        "name": product.name,
        "sku": product.sku,
        "brand": product.brand,
        "product_type": product.product_type,
        "category": {"id": product.category.id, "name": product.category.name, "slug": product.category.slug},
        "image": img,
        "hover_image": hover,
        "mrp": f"{mrp:.2f}",
        "price": f"{price:.2f}",
        "discount_pct": discount_pct(mrp, price),
        "rating_avg": float(product.rating_avg or 0),
        "rating_count": product.rating_count,
        "in_stock": total_avail > 0,
        "stock_status": stock_status(total_avail, threshold),
        "is_new_arrival": product.is_new_arrival,
        "is_bestseller": product.is_bestseller,
        "is_featured": product.is_featured,
        "badges": promo_badges_for(product, promos or []),
        "variant_count": len(active),
        "default_variant_id": default.id if default else None,
        "colors": colors[:6],
    }


def serialize_detail(db: Session, product: Product, promos: list[Promotion]) -> dict:
    card = serialize_card(product, promos)
    active = [v for v in product.variants if v.is_active]
    variants = []
    options: dict[str, dict] = {}
    attr_order: dict[str, int] = {}
    for v in active:
        price, mrp = variant_price(v), q(v.mrp)
        avail = v.inventory.available if v.inventory else 0
        attrs = {}
        for av in v.attribute_values:
            a = av.attribute
            attrs[a.code] = av.value
            if a.is_variant_axis:
                attr_order[a.code] = a.display_order
                opt = options.setdefault(a.code, {"code": a.code, "name": a.name, "display_type": a.display_type, "values": []})
                if not any(x["slug"] == av.slug for x in opt["values"]):
                    opt["values"].append({"value": av.value, "slug": av.slug, "hex": av.swatch_hex, "order": av.display_order})
        variants.append({
            "id": v.id,
            "sku": v.sku,
            "name": v.name,
            "mrp": f"{mrp:.2f}",
            "price": f"{price:.2f}",
            "discount_pct": discount_pct(mrp, price),
            "savings": f"{q(mrp - price):.2f}",
            "available": avail,
            "stock_status": stock_status(avail, v.inventory.low_stock_threshold if v.inventory else 5),
            "attributes": attrs,
            "is_default": v.is_default,
            "weight_grams": str(v.weight_grams) if v.weight_grams is not None else None,
            "image_urls": [i.url for i in product.images if i.variant_id == v.id],
        })
    for opt in options.values():
        opt["values"].sort(key=lambda x: x.pop("order", 0))
    # Product-level (non-axis) attributes shared by all variants, e.g. material, plating, fabric.
    shared: dict[str, str] = {}
    if active:
        first = {av.attribute.code: (av.attribute.name, av.value) for av in active[0].attribute_values if not av.attribute.is_variant_axis}
        for code, (name, value) in first.items():
            if all(any(av.attribute.code == code and av.value == value for av in v.attribute_values) for v in active):
                shared[name] = value
    crumbs = []
    c = product.category
    while c is not None:
        crumbs.insert(0, {"name": c.name, "slug": c.slug})
        c = c.parent
    rate = product.tax_rate.rate if product.tax_rate else Decimal("0")
    card.update({
        "description": product.description,
        "short_description": product.short_description,
        "specifications": {**shared, **(product.specifications or {})},
        "care_instructions": product.care_instructions,
        "size_chart": product.size_chart,
        "images": [
            {"id": i.id, "url": i.url, "alt": i.alt_text or product.name, "variant_id": i.variant_id}
            for i in sorted(product.images, key=lambda i: (not i.is_primary, i.display_order))
        ],
        "variants": variants,
        "options": sorted(options.values(), key=lambda o: attr_order.get(o["code"], 0)),
        "tax_rate": f"{q(rate):.2f}",
        "tax_inclusive": True,
        "hsn_code": product.tax_rate.hsn_code if product.tax_rate else None,
        "min_order_qty": product.min_order_qty,
        "max_order_qty": product.max_order_qty,
        "processing_days": product.processing_days,
        "is_returnable": product.is_returnable,
        "return_window_days": product.return_window_days,
        "is_cod_available": product.is_cod_available,
        "seo_title": product.seo_title or f"{product.name} | LoveVital",
        "seo_description": product.seo_description or (product.short_description or "")[:160],
        "breadcrumbs": crumbs,
        "tags": product.tags or [],
        "collections": [{"name": col.name, "slug": col.slug} for col in product.collections if col.is_active],
    })
    return card


def base_product_query():
    return (
        select(Product)
        .where(Product.status == "active")
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.attribute_values),
        )
    )


def _in_stock_clause():
    return exists().where(
        ProductVariant.product_id == Product.id,
        ProductVariant.is_active.is_(True),
        Inventory.variant_id == ProductVariant.id,
        Inventory.quantity_on_hand - Inventory.quantity_reserved > 0,
    )


def _attr_clause(code: str, slugs: list[str]):
    return exists().where(
        ProductVariant.product_id == Product.id,
        ProductVariant.is_active.is_(True),
        variant_attribute_values.c.variant_id == ProductVariant.id,
        variant_attribute_values.c.attribute_value_id == ProductAttributeValue.id,
        ProductAttributeValue.attribute_id == ProductAttribute.id,
        ProductAttribute.code == code,
        ProductAttributeValue.slug.in_(slugs),
    )


FILTER_ATTRS = ["color", "size", "material", "plating", "stone", "style", "fabric", "fit", "occasion"]
SORTS = {
    "popularity": [Product.sold_count.desc(), Product.rating_count.desc()],
    "newest": [Product.published_at.desc(), Product.id.desc()],
    "price_asc": [Product.price_min.asc()],
    "price_desc": [Product.price_min.desc()],
    "rating": [Product.rating_avg.desc(), Product.rating_count.desc()],
    "discount": [Product.max_discount_pct.desc()],
}


def search_conditions(db: Session, params: dict) -> tuple[list, dict]:
    conds = []
    ctx: dict = {}
    if params.get("q"):
        groups = expand_query(params["q"])
        for g in groups:
            conds.append(or_(*[func.lower(Product.search_text).like(f"%{t}%") for t in g]))
        ctx["query_groups"] = groups
    if params.get("category"):
        cat = db.scalar(select(Category).where(Category.slug == params["category"]))
        if cat:
            conds.append(Product.category_id.in_(category_descendant_ids(db, cat)))
            ctx["category"] = cat
        else:
            conds.append(Product.id == -1)
    if params.get("collection"):
        col = db.scalar(select(Collection).where(Collection.slug == params["collection"]))
        ctx["collection"] = col
        conds.append(
            exists().where(collection_products.c.product_id == Product.id,
                           collection_products.c.collection_id == (col.id if col else -1))
        )
    if params.get("product_type"):
        conds.append(Product.product_type == params["product_type"])
    if params.get("brand"):
        conds.append(Product.brand.in_(params["brand"]))
    if params.get("min_price") is not None:
        conds.append(Product.price_min >= D(params["min_price"]))
    if params.get("max_price") is not None:
        conds.append(Product.price_min <= D(params["max_price"]))
    if params.get("in_stock"):
        conds.append(_in_stock_clause())
    if params.get("min_rating"):
        conds.append(Product.rating_avg >= D(params["min_rating"]))
    if params.get("min_discount"):
        conds.append(Product.max_discount_pct >= int(params["min_discount"]))
    if params.get("on_sale"):
        conds.append(Product.max_discount_pct >= 1)
    if params.get("featured"):
        conds.append(Product.is_featured.is_(True))
    if params.get("bestseller"):
        conds.append(Product.is_bestseller.is_(True))
    if params.get("new_arrival"):
        conds.append(Product.is_new_arrival.is_(True))
    for code in FILTER_ATTRS:
        if params.get(code):
            conds.append(_attr_clause(code, params[code]))
    return conds, ctx


def list_products(db: Session, params: dict, page: int, page_size: int, sort: str) -> dict:
    conds, ctx = search_conditions(db, params)
    stmt = base_product_query().where(and_(*conds)) if conds else base_product_query()
    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(Product.id).order_by(None).subquery()))
    order = SORTS.get(sort, SORTS["popularity"])
    rows = db.scalars(stmt.order_by(*order, Product.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    promos = active_promotions(db)
    result = {
        "items": [serialize_card(p, promos) for p in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, math.ceil(total / page_size)) if total else 0,
        "facets": facets(db, params),
        "did_you_mean": None,
        "category": None,
        "collection": None,
    }
    if ctx.get("category"):
        c = ctx["category"]
        result["category"] = {
            "id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url,
            "seo_title": c.seo_title, "seo_description": c.seo_description,
            "parent": {"name": c.parent.name, "slug": c.parent.slug} if c.parent else None,
            "children": [{"name": ch.name, "slug": ch.slug} for ch in c.children if ch.is_active],
        }
    if ctx.get("collection"):
        col = ctx["collection"]
        result["collection"] = {"name": col.name, "slug": col.slug, "description": col.description, "image_url": col.image_url}
    if params.get("q") and total == 0:
        result["did_you_mean"] = suggest_correction(db, params["q"])
    return result


def facets(db: Session, params: dict) -> dict:
    """Facet values available within the current category/search/type scope (attribute filters ignored)."""
    scope = {k: params.get(k) for k in ("q", "category", "collection", "product_type", "on_sale", "new_arrival", "bestseller", "featured")}
    conds, _ = search_conditions(db, scope)
    base_ids = select(Product.id).where(Product.status == "active", *conds)
    brand_rows = db.execute(
        select(Product.brand, func.count()).where(Product.id.in_(base_ids)).group_by(Product.brand).order_by(Product.brand)
    ).all()
    price = db.execute(select(func.min(Product.price_min), func.max(Product.price_min)).where(Product.id.in_(base_ids))).one()
    attr_rows = db.execute(
        select(ProductAttribute.code, ProductAttribute.name, ProductAttributeValue.value, ProductAttributeValue.slug,
               ProductAttributeValue.swatch_hex, func.count(func.distinct(ProductVariant.product_id)))
        .join(ProductAttributeValue, ProductAttributeValue.attribute_id == ProductAttribute.id)
        .join(variant_attribute_values, variant_attribute_values.c.attribute_value_id == ProductAttributeValue.id)
        .join(ProductVariant, ProductVariant.id == variant_attribute_values.c.variant_id)
        .where(ProductVariant.product_id.in_(base_ids), ProductVariant.is_active.is_(True),
               ProductAttribute.is_filterable.is_(True), ProductAttribute.code.in_(FILTER_ATTRS))
        .group_by(ProductAttribute.code, ProductAttribute.name, ProductAttributeValue.value, ProductAttributeValue.slug,
                  ProductAttributeValue.swatch_hex, ProductAttribute.display_order, ProductAttributeValue.display_order)
        .order_by(ProductAttribute.display_order, ProductAttributeValue.display_order)
    ).all()
    attrs: dict[str, dict] = {}
    for code, name, value, slug, hex_, count in attr_rows:
        attrs.setdefault(code, {"code": code, "name": name, "values": []})["values"].append(
            {"value": value, "slug": slug, "hex": hex_, "count": count}
        )
    return {
        "brands": [{"value": b, "count": c} for b, c in brand_rows],
        "price": {"min": f"{q(price[0] or 0):.2f}", "max": f"{q(price[1] or 0):.2f}"},
        "attributes": list(attrs.values()),
    }


def vocabulary(db: Session) -> list[str]:
    words: set[str] = set(SYNONYMS)
    for (txt,) in db.execute(select(Product.search_text).where(Product.status == "active")).all():
        words.update(w for w in re.findall(r"[a-z]{3,}", txt or ""))
    return sorted(words)


def suggest_correction(db: Session, q_text: str) -> str | None:
    vocab = vocabulary(db)
    out, changed = [], False
    for tok in re.findall(r"[a-z0-9]+", q_text.lower()):
        if tok in vocab or len(tok) < 3:
            out.append(tok)
            continue
        m = difflib.get_close_matches(tok, vocab, n=1, cutoff=0.72)
        if m:
            out.append(m[0])
            changed = True
        else:
            out.append(tok)
    return " ".join(out) if changed else None


def suggestions(db: Session, q_text: str, limit: int = 8) -> dict:
    q_text = q_text.strip().lower()
    if len(q_text) < 2:
        return {"products": [], "categories": [], "queries": []}
    groups = expand_query(q_text)
    conds = [or_(*[func.lower(Product.search_text).like(f"%{t}%") for t in g]) for g in groups]
    prods = db.scalars(base_product_query().where(*conds).order_by(Product.sold_count.desc()).limit(limit)).unique().all()
    if not prods:
        fixed = suggest_correction(db, q_text)
        if fixed:
            groups = expand_query(fixed)
            conds = [or_(*[func.lower(Product.search_text).like(f"%{t}%") for t in g]) for g in groups]
            prods = db.scalars(base_product_query().where(*conds).order_by(Product.sold_count.desc()).limit(limit)).unique().all()
    cats = db.scalars(
        select(Category).where(Category.is_active.is_(True), func.lower(Category.name).like(f"%{q_text}%")).limit(4)
    ).all()
    queries = sorted({p.category.name.lower() for p in prods} | {g[0] for g in groups if g})[:5]
    return {
        "products": [
            {"slug": p.slug, "name": p.name, "image": _primary_images(p)[0], "price": f"{q(p.price_min):.2f}", "sku": p.sku}
            for p in prods
        ],
        "categories": [{"name": c.name, "slug": c.slug} for c in cats],
        "queries": queries,
    }


def related_products(db: Session, product: Product, limit: int = 8) -> list[Product]:
    return list(
        db.scalars(
            base_product_query()
            .where(Product.category_id == product.category_id, Product.id != product.id)
            .order_by(Product.sold_count.desc())
            .limit(limit)
        ).unique()
    )


def frequently_bought_together(db: Session, product: Product, limit: int = 3) -> list[Product]:
    """Co-purchase from order history; falls back to complementary product type."""
    from app.models import OrderItem

    sub = select(OrderItem.order_id).where(OrderItem.product_id == product.id)
    rows = db.execute(
        select(OrderItem.product_id, func.count().label("n"))
        .where(OrderItem.order_id.in_(sub), OrderItem.product_id != product.id, OrderItem.product_id.is_not(None))
        .group_by(OrderItem.product_id)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    ids = [r[0] for r in rows]
    found = list(db.scalars(base_product_query().where(Product.id.in_(ids))).unique()) if ids else []
    if len(found) < limit:
        other = "apparel" if product.product_type == "jewellery" else "jewellery"
        extra = db.scalars(
            base_product_query()
            .where(Product.product_type == other, Product.id.not_in([p.id for p in found] + [product.id]))
            .order_by(Product.is_bestseller.desc(), Product.sold_count.desc())
            .limit(limit - len(found))
        ).unique().all()
        found += list(extra)
    return found
