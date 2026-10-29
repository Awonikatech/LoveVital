"""Small shared services: store settings, audit log, slugs, notifications."""
import logging
import re
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, utcnow
from app.integrations.email import get_email_backend
from app.models import AuditLog, Notification, StoreSetting, User

log = logging.getLogger("app")

DEFAULT_SETTINGS: dict[str, tuple[Any, str, bool]] = {
    # key: (value, description, is_public)
    "store_name": ("LoveVital", "Storefront name", True),
    "store_tagline": ("Fine Artificial Jewellery & Couture", "Tagline", True),
    "announcement_text": (
        "Festive Edit is live — Flat 10% off with code FESTIVE10 · Free shipping above ₹999",
        "Announcement bar text",
        True,
    ),
    "free_shipping_threshold": ("999.00", "Default free-shipping threshold (₹)", True),
    "cod_fee": ("49.00", "Cash-on-delivery fee (₹)", True),
    "cod_max_order_value": ("15000.00", "Maximum order value for COD (₹)", True),
    "allow_coupon_with_promotions": (True, "Allow coupons to stack with automatic promotions", False),
    "low_stock_default_threshold": (5, "Default low-stock threshold", False),
    "return_window_days": (7, "Default return window (days)", True),
    "support_email": ("janviawadhesh@gmail.com", "Support email", True),
    "support_phone": ("+91-8744092015", "Support phone", True),
    "support_hours": ("Mon–Sat, 10am–7pm IST", "Support hours", True),
    "store_address": ("B1601, Samridhi Grand Avenue, Greater Noida (W), Uttar Pradesh 201305", "Registered address", True),
    "gstin": ("09ABCDE1234F1Z5", "Store GSTIN (demo)", True),
    "social_links": (
        {"instagram": "https://instagram.com/", "facebook": "https://facebook.com/", "pinterest": "https://pinterest.com/", "youtube": "https://youtube.com/"},
        "Social media URLs",
        True,
    ),
    "footer_links": (
        [
            {"label": "About Us", "href": "/pages/about"},
            {"label": "Contact Us", "href": "/pages/contact"},
            {"label": "FAQs", "href": "/pages/faq"},
            {"label": "Shipping Policy", "href": "/pages/shipping-policy"},
            {"label": "Returns & Refunds", "href": "/pages/return-policy"},
            {"label": "Privacy Policy", "href": "/pages/privacy-policy"},
        ],
        "Footer policy links",
        True,
    ),
    "testimonials": (
        [
            {"name": "Ananya R.", "city": "Bengaluru", "text": "The kundan set looked straight out of a heritage vault. Got compliments all evening at my cousin's sangeet!", "rating": 5},
            {"name": "Meher K.", "city": "Delhi", "text": "Beautiful packaging and the kurta fits perfectly. Delivery was a day earlier than promised.", "rating": 5},
            {"name": "Sneha P.", "city": "Pune", "text": "Lightweight jhumkas that don't hurt even after hours. The gold tone hasn't faded at all.", "rating": 4},
            {"name": "Farah S.", "city": "Hyderabad", "text": "Return was effortless and the refund hit my UPI in two days. Will definitely shop again.", "rating": 5},
        ],
        "Homepage testimonials",
        True,
    ),
}


def get_setting(db: Session, key: str, default: Any = None) -> Any:
    row = db.scalar(select(StoreSetting).where(StoreSetting.key == key))
    if row is not None:
        return row.value
    if key in DEFAULT_SETTINGS:
        return DEFAULT_SETTINGS[key][0]
    return default


def set_setting(db: Session, key: str, value: Any) -> StoreSetting:
    row = db.scalar(select(StoreSetting).where(StoreSetting.key == key))
    if row is None:
        desc, public = (DEFAULT_SETTINGS.get(key, (None, None, False)))[1:]
        row = StoreSetting(key=key, value=value, description=desc, is_public=bool(public))
        db.add(row)
    else:
        row.value = value
    return row


def audit(db: Session, actor: User | None, action: str, entity_type: str, entity_id: Any = None,
          changes: dict | None = None, ip: str | None = None) -> None:
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            changes=_jsonable(changes) if changes else None,
            ip_address=ip,
        )
    )


def _jsonable(obj: Any) -> Any:
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items() if k not in {"password", "password_hash", "token"}}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def send_email_task(template: str, to: str, subject: str, body: str, user_id: int | None = None) -> None:
    """Run as a FastAPI BackgroundTask — opens its own session."""
    db = SessionLocal()
    try:
        n = Notification(user_id=user_id, template=template, recipient=to, subject=subject, body=body, status="queued")
        db.add(n)
        db.flush()
        try:
            get_email_backend().send(to, subject, body)
            n.status, n.sent_at = "sent", utcnow()
        except Exception as e:  # never let email failures break the request
            n.status, n.error = "failed", str(e)[:500]
            log.warning("Email to %s failed: %s", to, e)
        db.commit()
    finally:
        db.close()
