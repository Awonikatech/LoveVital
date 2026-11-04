from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db, utcnow
from app.core.errors import NotFound
from app.core.rate_limit import rate_limit
from app.models import Banner, CmsPage, Collection, NewsletterSubscriber, Product, StoreSetting
from app.services import catalog_service
from app.services.common import DEFAULT_SETTINGS

router = APIRouter(tags=["content"])


def public_settings(db: Session) -> dict:
    out = {k: v[0] for k, v in DEFAULT_SETTINGS.items() if v[2]}
    for row in db.scalars(select(StoreSetting).where(StoreSetting.is_public.is_(True))).all():
        out[row.key] = row.value
    return out


@router.get("/settings/public")
def get_public_settings(db: Session = Depends(get_db)):
    from app.core.config import settings as cfg

    data = public_settings(db)
    data["payment_mode"] = cfg.RAZORPAY_MODE
    return data


def _active_banners(db: Session, placement: str | None = None) -> list[dict]:
    now = utcnow()
    stmt = select(Banner).where(Banner.is_active.is_(True), or_(Banner.starts_at.is_(None), Banner.starts_at <= now),
                                or_(Banner.ends_at.is_(None), Banner.ends_at > now)).order_by(Banner.display_order)
    if placement:
        stmt = stmt.where(Banner.placement == placement)
    return [{"id": b.id, "title": b.title, "subtitle": b.subtitle, "eyebrow": b.eyebrow, "image_url": b.image_url,
             "cta_text": b.cta_text, "cta_link": b.cta_link, "placement": b.placement} for b in db.scalars(stmt).all()]


@router.get("/banners")
def banners(placement: str | None = None, db: Session = Depends(get_db)):
    return _active_banners(db, placement)


@router.get("/home", summary="Everything the home page needs in one call")
def home(db: Session = Depends(get_db)):
    promos = catalog_service.active_promotions(db)
    q = catalog_service.base_product_query()

    def cards(stmt, n=8):
        return [catalog_service.serialize_card(p, promos) for p in db.scalars(stmt.limit(n)).unique().all()]

    from app.api.v1.catalog import categories as cat_tree

    now = utcnow()
    cols = [c for c in db.scalars(select(Collection).where(Collection.is_active.is_(True), Collection.is_featured.is_(True)).order_by(Collection.display_order)).all()
            if (not c.starts_at or c.starts_at <= now) and (not c.ends_at or c.ends_at > now)]
    return {
        "banners": _active_banners(db),
        "categories": cat_tree(db),
        "trending": cards(q.where(Product.is_featured.is_(True)).order_by(Product.sold_count.desc())),
        "best_sellers": cards(q.where(Product.is_bestseller.is_(True)).order_by(Product.sold_count.desc())),
        "new_arrivals": cards(q.where(Product.is_new_arrival.is_(True)).order_by(Product.published_at.desc())),
        "on_sale": cards(q.where(Product.max_discount_pct >= 40).order_by(Product.max_discount_pct.desc())),
        "collections": [{"name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url} for c in cols],
        "promotions": [{"name": p.name, "description": p.description, "badge": p.badge_text} for p in promos],
        "settings": public_settings(db),
    }


@router.get("/pages/{slug}")
def page(slug: str, db: Session = Depends(get_db)):
    p = db.scalar(select(CmsPage).where(CmsPage.slug == slug, CmsPage.is_published.is_(True)))
    if not p:
        raise NotFound("Page not found")
    return {"slug": p.slug, "title": p.title, "body": p.body, "seo_title": p.seo_title, "seo_description": p.seo_description,
            "updated_at": p.updated_at.isoformat()}


class NewsletterIn(BaseModel):
    email: EmailStr


@router.post("/newsletter", status_code=201, dependencies=[Depends(rate_limit("newsletter", 10, 3600))])
def subscribe(body: NewsletterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    sub = db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email == email))
    if sub:
        sub.status, sub.unsubscribed_at = "subscribed", None
    else:
        db.add(NewsletterSubscriber(email=email, status="subscribed", source="footer"))
    db.commit()
    return {"message": "You're on the list! Look out for exclusive offers in your inbox."}
