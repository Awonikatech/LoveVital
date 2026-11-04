"""Authentication: Argon2id passwords, short-lived JWT access tokens, rotating refresh tokens.

Refresh tokens are opaque random strings, stored only as SHA-256 hashes, delivered in an HttpOnly
cookie scoped to /api/v1/auth. Each refresh rotates the token; presenting an already-rotated token
(reuse) revokes the whole token family (likely theft)."""
from datetime import timedelta
import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import Conflict, Forbidden, Unauthorized, ValidationFailed
from app.core.security import (
    create_access_token,
    generate_token,
    hash_password,
    needs_rehash,
    sha256,
    verify_password,
)
from app.models import AuthToken, RefreshToken, Role, User


def user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "email_verified_at": user.email_verified_at,
        "roles": user.role_names,
        "permissions": sorted(user.permissions),
        "created_at": user.created_at,
    }


def get_role(db: Session, name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if not role:
        from app.core.deps import ROLE_PERMISSIONS

        role = Role(name=name, description=name.title(), permissions=ROLE_PERMISSIONS.get(name, []))
        db.add(role)
        db.flush()
    return role


def register(db: Session, full_name: str, email: str, password: str, phone: str | None) -> User:
    email = email.lower().strip()
    existing = db.scalar(select(User).where(User.email == email))
    if existing and not existing.is_guest:
        raise Conflict("An account with this email already exists. Try logging in.", code="email_taken")
    if existing:  # upgrade a guest-checkout record into a full account, keeping their orders
        user = existing
        user.is_guest = False
        user.full_name = full_name
        user.phone = phone or user.phone
        user.password_hash = hash_password(password)
    else:
        user = User(email=email, full_name=full_name, phone=phone, password_hash=hash_password(password))
        db.add(user)
    if not any(r.name == "customer" for r in user.roles):
        user.roles.append(get_role(db, "customer"))
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if not user or user.is_guest or not verify_password(password, user.password_hash if user else None):
        raise Unauthorized("Incorrect email or password", code="invalid_credentials")
    if not user.is_active:
        raise Forbidden("This account has been disabled. Please contact support.", code="account_disabled")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = utcnow()
    return user


def issue_tokens(db: Session, user: User, user_agent: str | None = None, family_id: str | None = None) -> tuple[str, str]:
    access = create_access_token(user.id, user.role_names)
    raw_refresh = generate_token(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=sha256(raw_refresh),
            family_id=family_id or secrets.token_hex(16),
            expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=(user_agent or "")[:255],
        )
    )
    return access, raw_refresh


def rotate_refresh(db: Session, raw_refresh: str | None, user_agent: str | None) -> tuple[User, str, str]:
    if not raw_refresh:
        raise Unauthorized("Session expired. Please log in again.", code="no_refresh_token")
    tok = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(raw_refresh)).with_for_update())
    if not tok:
        raise Unauthorized("Session expired. Please log in again.", code="invalid_refresh_token")
    if tok.revoked_at is not None:
        # Reuse of a rotated token -> revoke the entire family.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == tok.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        db.commit()
        raise Unauthorized("Session expired. Please log in again.", code="refresh_token_reused")
    if tok.expires_at < utcnow():
        raise Unauthorized("Session expired. Please log in again.", code="refresh_token_expired")
    user = db.get(User, tok.user_id)
    if not user or not user.is_active:
        raise Unauthorized("Account is not active", code="inactive_account")
    tok.revoked_at = utcnow()
    access, new_refresh = issue_tokens(db, user, user_agent, family_id=tok.family_id)
    return user, access, new_refresh


def revoke_refresh(db: Session, raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    tok = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(raw_refresh)))
    if tok and tok.revoked_at is None:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == tok.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )


def create_auth_token(db: Session, user: User, purpose: str, ttl: timedelta) -> str:
    raw = generate_token(32)
    db.add(AuthToken(user_id=user.id, purpose=purpose, token_hash=sha256(raw), expires_at=utcnow() + ttl))
    return raw


def consume_auth_token(db: Session, raw: str, purpose: str) -> User:
    tok = db.scalar(
        select(AuthToken).where(AuthToken.token_hash == sha256(raw), AuthToken.purpose == purpose).with_for_update()
    )
    if not tok or tok.used_at is not None or tok.expires_at < utcnow():
        raise ValidationFailed("This link is invalid or has expired. Please request a new one.", code="invalid_token")
    tok.used_at = utcnow()
    user = db.get(User, tok.user_id)
    if not user:
        raise ValidationFailed("This link is invalid or has expired.", code="invalid_token")
    return user


def reset_password(db: Session, raw: str, new_password: str) -> User:
    user = consume_auth_token(db, raw, "reset_password")
    user.password_hash = hash_password(new_password)
    # Log out everywhere after a reset.
    db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow())
    )
    return user
