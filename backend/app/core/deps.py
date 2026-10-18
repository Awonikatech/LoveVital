from collections.abc import Callable

import jwt
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.models import User

bearer = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["*"],
    "staff": [
        "dashboard:view",
        "products:read",
        "products:write",
        "inventory:read",
        "inventory:write",
        "orders:read",
        "orders:write",
        "customers:read",
        "returns:read",
        "returns:write",
        "content:write",
        "shipping:read",
        "coupons:read",
    ],
    "customer": [],
}
# Permissions that only full admins hold by default (cost price, money movement, settings):
#   products:cost, reports:view, refunds:write, coupons:write, shipping:write,
#   customers:write, settings:write, audit:read, users:write


def get_current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User | None:
    if not creds:
        return None
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Session expired", code="token_expired")
    except jwt.PyJWTError:
        raise Unauthorized("Invalid authentication token", code="invalid_token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise Unauthorized("Account is not active", code="inactive_account")
    return user


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if not user:
        raise Unauthorized("Please log in to continue")
    return user


def require_permission(*perms: str) -> Callable[..., User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if not user.is_staff:
            raise Forbidden("Administrator access required")
        missing = [p for p in perms if not user.has_permission(p)]
        if missing:
            raise Forbidden(f"Missing permission: {', '.join(missing)}")
        return user

    return checker


def cart_token_header(x_cart_token: str | None = Header(default=None)) -> str | None:
    return x_cart_token


def request_ip(request: Request) -> str | None:
    from app.core.rate_limit import client_ip

    return client_ip(request)
