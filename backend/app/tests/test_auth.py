"""Registration, login, token refresh/rotation, password reset and account state."""
from datetime import timedelta

from sqlalchemy import select

from app.models import RefreshToken, User
from app.services import auth_service
from app.tests.conftest import PASSWORD, make_user

API = "/api/v1/auth"


def _register(client, email="new.user@example.com", password="Secret123", **kw):
    return client.post(f"{API}/register", json={"full_name": "New User", "email": email, "password": password, **kw})


def _set_cookie_headers(resp) -> list[str]:
    return resp.headers.get_list("set-cookie")


def _refresh(client, refresh: str | None, csrf: str | None, send_header: bool = True):
    """Call /auth/refresh with an explicit cookie set (independent of the client's jar)."""
    client.cookies.clear()
    parts = []
    if refresh:
        parts.append(f"swk_refresh={refresh}")
    if csrf:
        parts.append(f"swk_csrf={csrf}")
    headers = {"Cookie": "; ".join(parts)} if parts else {}
    if send_header and csrf:
        headers["X-CSRF-Token"] = csrf
    return client.post(f"{API}/refresh", headers=headers)


def _session(resp) -> tuple[str, str]:
    return resp.cookies["swk_refresh"], resp.cookies["swk_csrf"]


# ----------------------------------------------------------------------------- register
def test_register_returns_token_and_sets_secure_cookies(client, catalog, outbox):
    r = _register(client, phone="9810012345")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"] and body["token_type"] == "bearer"
    assert body["user"]["email"] == "new.user@example.com"
    assert body["user"]["roles"] == ["customer"]

    cookies = _set_cookie_headers(r)
    refresh = next(c for c in cookies if c.startswith("swk_refresh="))
    csrf = next(c for c in cookies if c.startswith("swk_csrf="))
    assert "httponly" in refresh.lower()
    assert "path=/api/v1/auth" in refresh.lower()
    assert "httponly" not in csrf.lower()  # must be readable by JS for double-submit
    assert any(m["template"] == "verify_email" for m in outbox)


def test_register_duplicate_email_conflict(client, catalog):
    assert _register(client).status_code == 201
    r = _register(client, email="NEW.User@Example.com")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_register_rejects_weak_password(client, catalog):
    for pw in ("short1", "allletterspassword", "1234567890"):
        r = _register(client, password=pw)
        assert r.status_code == 422, pw
        assert r.json()["error"]["code"] == "validation_failed"


def test_password_is_stored_as_argon2_hash(client, catalog, db):
    _register(client, password="Secret123")
    user = db.scalar(select(User).where(User.email == "new.user@example.com"))
    assert user.password_hash.startswith("$argon2")
    assert "Secret123" not in user.password_hash


# ----------------------------------------------------------------------------- login & me
def test_login_success_and_me(client, users):
    r = client.post(f"{API}/login", json={"email": "PRIYA@test.example.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    me = client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "priya@test.example.com"


def test_login_wrong_password_and_unknown_user(client, users):
    r = client.post(f"{API}/login", json={"email": "priya@test.example.com", "password": "Wrong12345"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"
    r2 = client.post(f"{API}/login", json={"email": "nobody@test.example.com", "password": "Wrong12345"})
    assert r2.status_code == 401
    assert r2.json()["error"]["message"] == r.json()["error"]["message"]


def test_me_requires_token(client, users):
    assert client.get(f"{API}/me").status_code == 401
    r = client.get(f"{API}/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_disabled_account_cannot_log_in(client, db, users):
    users.customer.is_active = False
    db.commit()
    r = client.post(f"{API}/login", json={"email": users.customer.email, "password": PASSWORD})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "account_disabled"


def test_disabled_account_access_token_rejected(client, db, users, cust_h):
    users.customer.is_active = False
    db.commit()
    r = client.get(f"{API}/me", headers=cust_h)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "inactive_account"


# ----------------------------------------------------------------------------- refresh
def test_refresh_requires_matching_csrf_header(client, users):
    login = client.post(f"{API}/login", json={"email": users.customer.email, "password": PASSWORD})
    refresh, csrf = _session(login)

    r = _refresh(client, refresh, csrf, send_header=False)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"

    client.cookies.clear()
    r = client.post(f"{API}/refresh", headers={"Cookie": f"swk_refresh={refresh}; swk_csrf={csrf}", "X-CSRF-Token": "forged"})
    assert r.status_code == 403

    r = _refresh(client, refresh, csrf)
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_refresh_without_cookie_is_unauthorized(client, users):
    client.cookies.clear()
    r = client.post(f"{API}/refresh", headers={"X-CSRF-Token": "x"})
    assert r.status_code == 401


def test_refresh_rotation_and_reuse_revokes_family(client, users, db):
    login = client.post(f"{API}/login", json={"email": users.customer.email, "password": PASSWORD})
    r1, csrf1 = _session(login)

    first = _refresh(client, r1, csrf1)
    assert first.status_code == 200
    r2, csrf2 = _session(first)
    assert r2 != r1

    second = _refresh(client, r2, csrf2)
    assert second.status_code == 200
    r3, csrf3 = _session(second)

    # Replaying the already-rotated r1 is treated as theft: whole family revoked.
    reuse = _refresh(client, r1, csrf3)
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "refresh_token_reused"

    newest = _refresh(client, r3, csrf3)
    assert newest.status_code == 401

    db.expire_all()
    tokens = db.scalars(select(RefreshToken).where(RefreshToken.user_id == users.customer.id)).all()
    assert len(tokens) == 3
    assert all(t.revoked_at is not None for t in tokens)
    assert len({t.family_id for t in tokens}) == 1


def test_logout_revokes_refresh_token(client, users):
    login = client.post(f"{API}/login", json={"email": users.customer.email, "password": PASSWORD})
    refresh, csrf = _session(login)
    client.cookies.clear()
    out = client.post(f"{API}/logout", headers={"Cookie": f"swk_refresh={refresh}; swk_csrf={csrf}", "X-CSRF-Token": csrf})
    assert out.status_code == 200
    assert _refresh(client, refresh, csrf).status_code == 401


# ----------------------------------------------------------------------------- password reset
def test_forgot_password_does_not_reveal_accounts(client, users, outbox):
    known = client.post(f"{API}/forgot-password", json={"email": users.customer.email})
    unknown = client.post(f"{API}/forgot-password", json={"email": "ghost@test.example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert [m["to"] for m in outbox if m["template"] == "reset_password"] == [users.customer.email]


def test_reset_password_with_token(client, db, users):
    raw = auth_service.create_auth_token(db, users.customer, "reset_password", timedelta(hours=1))
    db.commit()
    login = client.post(f"{API}/login", json={"email": users.customer.email, "password": PASSWORD})
    old_refresh, csrf = _session(login)

    r = client.post(f"{API}/reset-password", json={"token": raw, "password": "BrandNew456"})
    assert r.status_code == 200, r.text

    assert client.post(f"{API}/login", json={"email": users.customer.email, "password": PASSWORD}).status_code == 401
    assert client.post(f"{API}/login", json={"email": users.customer.email, "password": "BrandNew456"}).status_code == 200
    # sessions issued before the reset are revoked
    assert _refresh(client, old_refresh, csrf).status_code == 401
    # token is single-use
    again = client.post(f"{API}/reset-password", json={"token": raw, "password": "Another789"})
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "invalid_token"


def test_reset_password_rejects_expired_or_wrong_purpose_token(client, db, users):
    expired = auth_service.create_auth_token(db, users.customer, "reset_password", timedelta(seconds=-1))
    verify = auth_service.create_auth_token(db, users.customer, "verify_email", timedelta(hours=1))
    db.commit()
    for raw in (expired, verify):
        r = client.post(f"{API}/reset-password", json={"token": raw, "password": "BrandNew456"})
        assert r.status_code == 422


def test_guest_record_can_be_upgraded_by_registration(client, db, catalog):
    make_user(db, "guest@example.com", password="Unused123", is_guest=True)
    db.commit()
    assert client.post(f"{API}/login", json={"email": "guest@example.com", "password": "Unused123"}).status_code == 401
    assert _register(client, email="guest@example.com").status_code == 201
