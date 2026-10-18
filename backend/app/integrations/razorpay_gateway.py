"""Payment gateway adapter.

`RazorpayGateway` wraps the official `razorpay` Python SDK (test or live keys).
`MockRazorpayGateway` reproduces Razorpay's ids and HMAC-SHA256 signature scheme locally so the
exact same verification code path is exercised without network access or credentials.

Razorpay signature rules (https://razorpay.com/docs/payments/server-integration/python/):
  * Checkout callback: HMAC_SHA256(key_secret, f"{razorpay_order_id}|{razorpay_payment_id}")
  * Webhook:            HMAC_SHA256(webhook_secret, raw_request_body)  -> header X-Razorpay-Signature
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import settings
from app.core.security import constant_time_equals, hmac_sha256_hex


class GatewayError(Exception):
    pass


@dataclass
class GatewayOrder:
    id: str
    amount: int
    currency: str
    status: str
    receipt: str


class PaymentGateway(Protocol):
    mode: str
    key_id: str

    def create_order(self, amount_paise: int, currency: str, receipt: str, notes: dict) -> GatewayOrder: ...
    def fetch_payment(self, payment_id: str) -> dict[str, Any]: ...
    def refund(self, payment_id: str, amount_paise: int, notes: dict, idempotency_key: str) -> dict[str, Any]: ...

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool: ...
    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool: ...


class _SignatureMixin:
    key_secret: str
    webhook_secret: str

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        if not (order_id and payment_id and signature):
            return False
        expected = hmac_sha256_hex(self.key_secret, f"{order_id}|{payment_id}")
        return constant_time_equals(expected, signature)

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        if not signature:
            return False
        expected = hmac_sha256_hex(self.webhook_secret, raw_body)
        return constant_time_equals(expected, signature)


class RazorpayGateway(_SignatureMixin):
    def __init__(self, key_id: str, key_secret: str, webhook_secret: str, mode: str):
        import razorpay  # imported lazily so mock mode needs no network setup

        self.mode = mode
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self.client = razorpay.Client(auth=(key_id, key_secret))
        self.client.set_app_details({"title": settings.APP_NAME, "version": "1.0"})

    def create_order(self, amount_paise: int, currency: str, receipt: str, notes: dict) -> GatewayOrder:
        try:
            o = self.client.order.create(
                {"amount": amount_paise, "currency": currency, "receipt": receipt, "notes": notes, "payment_capture": 1}
            )
        except Exception as e:  # razorpay.errors.* — keep the message, never the credentials
            raise GatewayError(f"Razorpay order creation failed: {e}") from e
        return GatewayOrder(o["id"], o["amount"], o["currency"], o["status"], o.get("receipt", receipt))

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        try:
            return self.client.payment.fetch(payment_id)
        except Exception as e:
            raise GatewayError(f"Razorpay payment fetch failed: {e}") from e

    def refund(self, payment_id: str, amount_paise: int, notes: dict, idempotency_key: str) -> dict[str, Any]:
        try:
            return self.client.payment.refund(
                payment_id, {"amount": amount_paise, "speed": "normal", "notes": notes, "receipt": idempotency_key[:40]}
            )
        except Exception as e:
            raise GatewayError(f"Razorpay refund failed: {e}") from e


class MockRazorpayGateway(_SignatureMixin):
    """Deterministic local simulator. State lives in-process (fine for dev/tests)."""

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str):
        self.mode = "mock"
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self._orders: dict[str, dict] = {}
        self._payments: dict[str, dict] = {}
        self._refunds_by_key: dict[str, dict] = {}

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(7)}"

    def create_order(self, amount_paise: int, currency: str, receipt: str, notes: dict) -> GatewayOrder:
        if amount_paise < 100:
            raise GatewayError("Order amount less than minimum amount allowed (₹1)")
        oid = self._id("order_mock")
        self._orders[oid] = {"id": oid, "amount": amount_paise, "currency": currency, "receipt": receipt, "status": "created"}
        return GatewayOrder(oid, amount_paise, currency, "created", receipt)

    # --- simulator helpers (mock-mode only endpoints use these) ---
    def simulate_payment(self, order_id: str, amount_paise: int, method: str, succeed: bool) -> dict[str, Any]:
        pid = self._id("pay_mock")
        status = "captured" if succeed else "failed"
        payment = {
            "id": pid,
            "order_id": order_id,
            "amount": amount_paise,
            "currency": "INR",
            "status": status,
            "method": method,
            "captured": succeed,
            "error_code": None if succeed else "BAD_REQUEST_ERROR",
            "error_description": None if succeed else "Payment was declined by the simulated bank.",
            "created_at": int(time.time()),
        }
        self._payments[pid] = payment
        if order_id in self._orders and succeed:
            self._orders[order_id]["status"] = "paid"
        sig = hmac_sha256_hex(self.key_secret, f"{order_id}|{pid}") if succeed else None
        return {"payment": payment, "signature": sig}

    def build_webhook(self, event: str, entity: dict[str, Any], entity_name: str = "payment") -> tuple[bytes, str, str]:
        event_id = self._id("evt_mock")
        body = json.dumps(
            {"entity": "event", "event": event, "payload": {entity_name: {"entity": entity}}, "created_at": int(time.time())}
        ).encode()
        return body, hmac_sha256_hex(self.webhook_secret, body), event_id

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        p = self._payments.get(payment_id)
        if not p:
            raise GatewayError("The id provided does not exist")
        return p

    def refund(self, payment_id: str, amount_paise: int, notes: dict, idempotency_key: str) -> dict[str, Any]:
        if idempotency_key in self._refunds_by_key:
            return self._refunds_by_key[idempotency_key]
        rid = self._id("rfnd_mock")
        r = {"id": rid, "payment_id": payment_id, "amount": amount_paise, "status": "processed", "notes": notes}
        self._refunds_by_key[idempotency_key] = r
        return r


_gateway: PaymentGateway | None = None


def get_gateway() -> PaymentGateway:
    global _gateway
    if _gateway is None:
        if settings.RAZORPAY_MODE == "mock":
            _gateway = MockRazorpayGateway(
                settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET, settings.RAZORPAY_WEBHOOK_SECRET
            )
        else:
            _gateway = RazorpayGateway(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET,
                settings.RAZORPAY_WEBHOOK_SECRET,
                settings.RAZORPAY_MODE,
            )
    return _gateway


def set_gateway(gw: PaymentGateway | None) -> None:
    """Test hook."""
    global _gateway
    _gateway = gw
