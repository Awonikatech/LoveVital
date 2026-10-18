from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFound
from app.models import Address, Product, ProductReview, User, Wishlist, WishlistItem
from app.schemas.common import AddressIn, AddressOut
from app.services import catalog_service

router = APIRouter(prefix="/account", tags=["account"])


def _apply_defaults(db: Session, user: User, addr: Address) -> None:
    if addr.is_default_shipping:
        db.execute(update(Address).where(Address.user_id == user.id, Address.id != addr.id).values(is_default_shipping=False))
    if addr.is_default_billing:
        db.execute(update(Address).where(Address.user_id == user.id, Address.id != addr.id).values(is_default_billing=False))


@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Address).where(Address.user_id == user.id).order_by(Address.is_default_shipping.desc(), Address.id.desc())).all()


@router.post("/addresses", response_model=AddressOut, status_code=201)
def create_address(body: AddressIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    first = not db.scalar(select(Address.id).where(Address.user_id == user.id).limit(1))
    addr = Address(user_id=user.id, **body.model_dump())
    if first:
        addr.is_default_shipping = addr.is_default_billing = True
    db.add(addr)
    db.flush()
    _apply_defaults(db, user, addr)
    db.commit()
    db.refresh(addr)
    return addr


def _own(db: Session, user: User, address_id: int) -> Address:
    a = db.get(Address, address_id)
    if not a or a.user_id != user.id:
        raise NotFound("Address not found")
    return a


@router.put("/addresses/{address_id}", response_model=AddressOut)
def update_address(address_id: int, body: AddressIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _own(db, user, address_id)
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    _apply_defaults(db, user, a)
    db.commit()
    db.refresh(a)
    return a


@router.delete("/addresses/{address_id}", status_code=204)
def delete_address(address_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_own(db, user, address_id))
    db.commit()


def _wishlist(db: Session, user: User) -> Wishlist:
    wl = db.scalar(select(Wishlist).where(Wishlist.user_id == user.id))
    if not wl:
        wl = Wishlist(user_id=user.id)
        db.add(wl)
        db.flush()
    return wl


@router.get("/wishlist")
def get_wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wl = _wishlist(db, user)
    db.commit()
    promos = catalog_service.active_promotions(db)
    items = [i for i in wl.items if i.product.status == "active"]
    return {"items": [{"id": i.id, "product": catalog_service.serialize_card(i.product, promos), "variant_id": i.variant_id,
                       "added_at": i.created_at.isoformat()} for i in sorted(items, key=lambda i: i.id, reverse=True)],
            "product_ids": [i.product_id for i in wl.items]}


class WishlistIn(BaseModel):
    product_id: int
    variant_id: int | None = None


@router.post("/wishlist", status_code=201)
def add_wishlist(body: WishlistIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.get(Product, body.product_id):
        raise NotFound("Product not found")
    wl = _wishlist(db, user)
    if not any(i.product_id == body.product_id for i in wl.items):
        wl.items.append(WishlistItem(product_id=body.product_id, variant_id=body.variant_id))
    db.commit()
    return {"product_ids": [i.product_id for i in wl.items]}


@router.delete("/wishlist/{product_id}")
def remove_wishlist(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wl = _wishlist(db, user)
    wl.items = [i for i in wl.items if i.product_id != product_id]
    db.commit()
    return {"product_ids": [i.product_id for i in wl.items]}


@router.get("/reviews")
def my_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ProductReview).where(ProductReview.user_id == user.id).order_by(ProductReview.created_at.desc())).all()
    out = []
    for r in rows:
        p = db.get(Product, r.product_id)
        out.append({"id": r.id, "rating": r.rating, "title": r.title, "body": r.body, "status": r.status,
                    "product": {"name": p.name, "slug": p.slug, "image": catalog_service._primary_images(p)[0]} if p else None,
                    "created_at": r.created_at.isoformat()})
    return out
