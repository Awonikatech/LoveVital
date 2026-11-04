from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Header, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, utcnow
from app.core.deps import get_current_user
from app.core.errors import Forbidden, Unauthorized
from app.core.rate_limit import rate_limit
from app.core.security import constant_time_equals, generate_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import (
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    ProfileUpdateIn,
    RegisterIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
    VerifyEmailIn,
)
from app.schemas.common import Message
from app.services import auth_service, cart_service
from app.services.common import send_email_task

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "swk_refresh"
CSRF_COOKIE = "swk_csrf"


def _set_session_cookies(response: Response, refresh: str) -> None:
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    common = dict(secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, domain=settings.COOKIE_DOMAIN)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=max_age, httponly=True, path=f"{settings.API_V1_PREFIX}/auth", **common)
    # Double-submit CSRF token: readable by JS, must be echoed in X-CSRF-Token for cookie-authenticated calls.
    response.set_cookie(CSRF_COOKIE, generate_token(24), max_age=max_age, httponly=False, path="/", **common)


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=f"{settings.API_V1_PREFIX}/auth", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=settings.COOKIE_DOMAIN)


def _check_csrf(csrf_cookie: str | None, csrf_header: str | None) -> None:
    if not csrf_cookie or not csrf_header or not constant_time_equals(csrf_cookie, csrf_header):
        raise Forbidden("CSRF validation failed", code="csrf_failed")


def _token_response(user: User, access: str) -> dict:
    return {
        "access_token": access,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": auth_service.user_payload(user),
    }


def _send_verification(background: BackgroundTasks, db: Session, user: User) -> None:
    raw = auth_service.create_auth_token(db, user, "verify_email", timedelta(days=2))
    link = f"{settings.FRONTEND_URL}/verify-email?token={raw}"
    background.add_task(
        send_email_task, "verify_email", user.email, "Verify your LoveVital account",
        f"Hi {user.full_name},\n\nWelcome to LoveVital! Please verify your email:\n{link}\n\nThis link expires in 48 hours.",
        user.id,
    )


@router.post("/register", response_model=TokenOut, status_code=201,
             dependencies=[Depends(rate_limit("register", 10, 3600))])
def register(body: RegisterIn, request: Request, response: Response, background: BackgroundTasks,
             x_cart_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = auth_service.register(db, body.full_name, body.email, body.password, body.phone)
    access, refresh = auth_service.issue_tokens(db, user, request.headers.get("user-agent"))
    cart_service.merge_guest_cart(db, user, x_cart_token)
    _send_verification(background, db, user)
    db.commit()
    _set_session_cookies(response, refresh)
    return _token_response(user, access)


@router.post("/login", response_model=TokenOut, dependencies=[Depends(rate_limit("login", 10, 300))])
def login(body: LoginIn, request: Request, response: Response,
          x_cart_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, body.email, body.password)
    access, refresh = auth_service.issue_tokens(db, user, request.headers.get("user-agent"))
    cart_service.merge_guest_cart(db, user, x_cart_token)
    db.commit()
    _set_session_cookies(response, refresh)
    return _token_response(user, access)


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(rate_limit("refresh", 60, 60))])
def refresh(request: Request, response: Response, db: Session = Depends(get_db),
            swk_refresh: str | None = Cookie(default=None), swk_csrf: str | None = Cookie(default=None),
            x_csrf_token: str | None = Header(default=None)):
    if not swk_refresh:
        raise Unauthorized("Not logged in", code="no_refresh_token")
    _check_csrf(swk_csrf, x_csrf_token)
    user, access, new_refresh = auth_service.rotate_refresh(db, swk_refresh, request.headers.get("user-agent"))
    db.commit()
    _set_session_cookies(response, new_refresh)
    return _token_response(user, access)


@router.post("/logout", response_model=Message)
def logout(response: Response, db: Session = Depends(get_db), swk_refresh: str | None = Cookie(default=None),
           swk_csrf: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    if swk_refresh:
        _check_csrf(swk_csrf, x_csrf_token)
        auth_service.revoke_refresh(db, swk_refresh)
        db.commit()
    _clear_session_cookies(response)
    return {"message": "Logged out"}


@router.post("/forgot-password", response_model=Message, dependencies=[Depends(rate_limit("forgot", 5, 900))])
def forgot_password(body: ForgotPasswordIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and user.is_active and not user.is_guest:
        raw = auth_service.create_auth_token(db, user, "reset_password", timedelta(hours=1))
        link = f"{settings.FRONTEND_URL}/reset-password?token={raw}"
        background.add_task(
            send_email_task, "reset_password", user.email, "Reset your LoveVital password",
            f"Hi {user.full_name},\n\nUse this link to set a new password (valid for 1 hour):\n{link}\n\n"
            "If you didn't request this, you can safely ignore this email.",
            user.id,
        )
        db.commit()
    # Same response either way — no account enumeration.
    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password", response_model=Message, dependencies=[Depends(rate_limit("reset", 10, 900))])
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)):
    auth_service.reset_password(db, body.token, body.password)
    db.commit()
    return {"message": "Your password has been updated. Please log in."}


@router.post("/verify-email", response_model=Message)
def verify_email(body: VerifyEmailIn, db: Session = Depends(get_db)):
    user = auth_service.consume_auth_token(db, body.token, "verify_email")
    user.email_verified_at = user.email_verified_at or utcnow()
    db.commit()
    return {"message": "Email verified. Thank you!"}


@router.post("/resend-verification", response_model=Message, dependencies=[Depends(rate_limit("resend", 3, 900))])
def resend_verification(background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.email_verified_at:
        _send_verification(background, db, user)
        db.commit()
    return {"message": "Verification email sent."}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return auth_service.user_payload(user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.full_name:
        user.full_name = body.full_name
    if body.phone is not None:
        user.phone = body.phone
    db.commit()
    return auth_service.user_payload(user)


@router.post("/change-password", response_model=Message, dependencies=[Depends(rate_limit("chpw", 10, 900))])
def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise Unauthorized("Current password is incorrect", code="invalid_credentials")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Password changed"}
