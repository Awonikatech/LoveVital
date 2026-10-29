"""Payment gateway (Razorpay) settings: mode and API keys, editable by administrators.

Secrets are encrypted at rest and never returned — the API only reports whether one is set and its last 4 characters.
Leaving a secret blank on save keeps the stored one."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import request_ip, require_permission
from app.core.errors import ValidationFailed
from app.core.security import encrypt_secret
from app.integrations import razorpay_gateway as rzp
from app.models import User
from app.services.common import audit, get_setting, set_setting

router = APIRouter(prefix="/payment-gateway", tags=["admin: payments"])

Mode = Literal["mock", "test", "live"]


def _hint(secret: str | None) -> str | None:
    return f"••••{secret[-4:]}" if secret and len(secret) > 8 else ("••••" if secret else None)


def _view(db: Session) -> dict:
    cfg = rzp.load_config(db)
    real = cfg.mode != "mock"
    return {
        "mode": cfg.mode,
        "source": cfg.source,
        "key_id": cfg.key_id if real else "",
        "key_secret_set": real and bool(cfg.key_secret),
        "key_secret_hint": _hint(cfg.key_secret) if real else None,
        "webhook_secret_set": real and bool(cfg.webhook_secret),
        "webhook_secret_hint": _hint(cfg.webhook_secret) if real else None,
        "webhook_url": f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/payments/razorpay/webhook",
        "webhook_events": ["payment.captured", "payment.failed", "refund.processed", "refund.failed"],
        "production": settings.is_production,
    }


class GatewayIn(BaseModel):
    mode: Mode
    key_id: str = Field("", max_length=64)
    key_secret: str | None = Field(None, max_length=128)  # blank/None = keep the stored one
    webhook_secret: str | None = Field(None, max_length=128)


def _resolve(db: Session, body: GatewayIn) -> rzp.GatewayConfig:
    """Merge submitted values with what is stored, and validate."""
    current = rzp.load_config(db)
    if body.mode == "mock":
        if settings.is_production:
            raise ValidationFailed("Mock payments can't be enabled in production", code="mock_in_production")
        return rzp.GatewayConfig("mock", "rzp_mock_key", "mock_secret_change_me", "mock_webhook_secret", "admin")
    key_id = body.key_id.strip()
    prefix = f"rzp_{body.mode}_"
    if not key_id.startswith(prefix):
        raise ValidationFailed(f"A {body.mode}-mode Key ID starts with “{prefix}”", code="invalid_key_id")
    same_key = current.mode != "mock" and current.key_id == key_id
    key_secret = (body.key_secret or "").strip() or (current.key_secret if same_key else "")
    if not key_secret:
        raise ValidationFailed("Enter the Key Secret for this Key ID", code="key_secret_required")
    webhook_secret = (body.webhook_secret or "").strip() or (current.webhook_secret if current.mode != "mock" else "")
    if body.mode == "live" and not webhook_secret:
        raise ValidationFailed("Live mode needs a webhook secret so payments are confirmed even if the customer closes the page",
                               code="webhook_secret_required")
    return rzp.GatewayConfig(body.mode, key_id, key_secret, webhook_secret, "admin")


def _check(cfg: rzp.GatewayConfig) -> None:
    if cfg.mode == "mock":
        return
    try:
        rzp.build_gateway(cfg).check_credentials()
    except rzp.GatewayError as e:
        raise ValidationFailed(f"Razorpay rejected these keys: {e}", code="gateway_auth_failed")


@router.get("")
def get_gateway_settings(user: User = Depends(require_permission("settings:write")), db: Session = Depends(get_db)):
    return _view(db)


@router.put("")
def save_gateway_settings(body: GatewayIn, request: Request, user: User = Depends(require_permission("settings:write")),
                          db: Session = Depends(get_db)):
    cfg = _resolve(db, body)
    _check(cfg)  # never save keys that can't take a payment
    stored = {"mode": cfg.mode}
    if cfg.mode != "mock":
        stored.update(key_id=cfg.key_id, key_secret=encrypt_secret(cfg.key_secret),
                      webhook_secret=encrypt_secret(cfg.webhook_secret) if cfg.webhook_secret else None)
    set_setting(db, rzp.SETTING_KEY, stored)
    audit(db, user, "settings.payment_gateway", "settings", rzp.SETTING_KEY,
          {"mode": cfg.mode, "key_id": cfg.key_id if cfg.mode != "mock" else None,
           "key_secret_changed": bool(body.key_secret), "webhook_secret_changed": bool(body.webhook_secret)},
          request_ip(request))
    db.commit()
    rzp.reload_gateway(db)
    return _view(db)


@router.post("/test")
def test_gateway_settings(body: GatewayIn, user: User = Depends(require_permission("settings:write")), db: Session = Depends(get_db)):
    """Check keys against Razorpay without saving them."""
    cfg = _resolve(db, body)
    _check(cfg)
    return {"ok": True, "message": "Simulator — no keys needed." if cfg.mode == "mock" else f"Connected to Razorpay ({cfg.mode} mode)."}


@router.delete("")
def reset_gateway_settings(request: Request, user: User = Depends(require_permission("settings:write")), db: Session = Depends(get_db)):
    """Forget the admin-entered settings and fall back to the RAZORPAY_* environment variables."""
    if get_setting(db, rzp.SETTING_KEY) is not None:
        set_setting(db, rzp.SETTING_KEY, None)
        audit(db, user, "settings.payment_gateway", "settings", rzp.SETTING_KEY, {"reset_to_env": True}, request_ip(request))
        db.commit()
    rzp.reload_gateway(db)
    return _view(db)
