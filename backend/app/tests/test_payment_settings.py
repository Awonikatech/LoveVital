"""Admin-managed payment gateway settings: validation, secret handling, and switching the live gateway."""
import pytest

from app.integrations import razorpay_gateway as rzp
from app.models import StoreSetting
from app.tests.conftest import place_order, start_payment

API = "/api/v1/admin/payment-gateway"
GLD = "JW-EAR-001-GLD"


@pytest.fixture
def keys_ok(monkeypatch):
    """Pretend Razorpay accepts any keys (no network in tests)."""
    calls = []
    monkeypatch.setattr(rzp.RazorpayGateway, "check_credentials", lambda self: calls.append(self.key_id))
    return calls


def test_defaults_to_env_mock(client, admin_h):
    r = client.get(API, headers=admin_h)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "mock" and body["source"] == "env"
    assert body["webhook_url"].endswith("/api/v1/payments/razorpay/webhook")


def test_staff_cannot_read_or_change(client, staff_h):
    assert client.get(API, headers=staff_h).status_code == 403
    assert client.put(API, headers=staff_h, json={"mode": "mock"}).status_code == 403


def test_save_test_keys_encrypts_and_masks(client, db, admin_h, keys_ok):
    r = client.put(API, headers=admin_h, json={"mode": "test", "key_id": "rzp_test_abc123", "key_secret": "supersecretvalue1234",
                                               "webhook_secret": "whsec_value_5678"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {**body, "mode": "test", "source": "admin", "key_id": "rzp_test_abc123", "key_secret_set": True,
                    "key_secret_hint": "••••1234", "webhook_secret_hint": "••••5678"}
    assert "supersecretvalue1234" not in r.text
    row = db.query(StoreSetting).filter_by(key=rzp.SETTING_KEY).one()
    assert "supersecretvalue1234" not in str(row.value)
    gw = rzp.get_gateway(db)
    assert isinstance(gw, rzp.RazorpayGateway) and gw.key_secret == "supersecretvalue1234" and gw.mode == "test"
    assert keys_ok == ["rzp_test_abc123"]


def test_blank_secret_keeps_stored_one(client, db, admin_h, keys_ok):
    client.put(API, headers=admin_h, json={"mode": "test", "key_id": "rzp_test_abc123", "key_secret": "supersecretvalue1234"})
    r = client.put(API, headers=admin_h, json={"mode": "test", "key_id": "rzp_test_abc123", "key_secret": ""})
    assert r.status_code == 200
    assert rzp.get_gateway(db).key_secret == "supersecretvalue1234"
    # A different Key ID needs its own secret.
    r = client.put(API, headers=admin_h, json={"mode": "test", "key_id": "rzp_test_other99"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "key_secret_required"


@pytest.mark.parametrize("payload, code", [
    ({"mode": "test", "key_id": "rzp_live_abc", "key_secret": "x" * 20}, "invalid_key_id"),
    ({"mode": "live", "key_id": "rzp_live_abc", "key_secret": "x" * 20}, "webhook_secret_required"),
])
def test_validation(client, admin_h, keys_ok, payload, code):
    r = client.put(API, headers=admin_h, json=payload)
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_rejected_keys_are_not_saved(client, db, admin_h, monkeypatch):
    def boom(self):
        raise rzp.GatewayError("Authentication failed")
    monkeypatch.setattr(rzp.RazorpayGateway, "check_credentials", boom)
    r = client.put(API, headers=admin_h, json={"mode": "test", "key_id": "rzp_test_abc", "key_secret": "wrongsecret12345"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "gateway_auth_failed"
    assert client.get(API, headers=admin_h).json()["source"] == "env"


def test_checkout_uses_admin_keys_and_public_mode(client, catalog, users, cust_h, admin_h, keys_ok, monkeypatch):
    created = []

    def fake_create(self, amount, currency, receipt, notes):
        created.append(self.key_id)
        return rzp.GatewayOrder("order_real123", amount, currency, "created", receipt)
    monkeypatch.setattr(rzp.RazorpayGateway, "create_order", fake_create)
    client.put(API, headers=admin_h, json={"mode": "test", "key_id": "rzp_test_abc123", "key_secret": "supersecretvalue1234"})
    assert client.get("/api/v1/settings/public").json()["payment_mode"] == "test"
    order = place_order(client, cust_h, [(catalog.vid(GLD), 1)])
    po = start_payment(client, cust_h, order)
    assert po["mode"] == "test" and po["key_id"] == "rzp_test_abc123" and po["razorpay_order_id"] == "order_real123"
    assert created == ["rzp_test_abc123"]
    # The mock simulator is closed once real keys are active.
    r = client.post("/api/v1/payments/razorpay/mock-checkout", json={"razorpay_order_id": "order_real123"})
    assert r.status_code == 404


def test_reset_returns_to_env(client, db, admin_h, keys_ok):
    client.put(API, headers=admin_h, json={"mode": "test", "key_id": "rzp_test_abc123", "key_secret": "supersecretvalue1234"})
    r = client.delete(API, headers=admin_h)
    assert r.json()["source"] == "env" and r.json()["mode"] == "mock"
    assert isinstance(rzp.get_gateway(db), rzp.MockRazorpayGateway)
