"""Login rate limiting (enabled only for this module; every other test runs with it off)."""
import pytest

from app.core.config import settings
from app.core.rate_limit import reset_rate_limits
from app.tests.conftest import PASSWORD


@pytest.fixture
def rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_eleventh_login_attempt_is_rate_limited(client, users, rate_limited):
    for i in range(10):
        r = client.post("/api/v1/auth/login", json={"email": users.customer.email, "password": f"Wrong{i}pass"})
        assert r.status_code == 401, (i, r.text)
    r = client.post("/api/v1/auth/login", json={"email": users.customer.email, "password": PASSWORD})
    assert r.status_code == 429
    err = r.json()["error"]
    assert err["code"] == "rate_limited"
    assert 1 <= err["details"]["retry_after"] <= 301


def test_rate_limit_is_per_client_ip(client, users, rate_limited):
    for _ in range(10):
        client.post("/api/v1/auth/login", json={"email": users.customer.email, "password": "Wrong1pass"},
                    headers={"X-Forwarded-For": "10.0.0.1"})
    blocked = client.post("/api/v1/auth/login", json={"email": users.customer.email, "password": PASSWORD},
                          headers={"X-Forwarded-For": "10.0.0.1"})
    other = client.post("/api/v1/auth/login", json={"email": users.customer.email, "password": PASSWORD},
                        headers={"X-Forwarded-For": "10.0.0.2"})
    assert blocked.status_code == 429
    assert other.status_code == 200


def test_rate_limit_disabled_by_default_in_tests(client, users):
    for _ in range(12):
        r = client.post("/api/v1/auth/login", json={"email": users.customer.email, "password": "Wrong1pass"})
        assert r.status_code == 401
