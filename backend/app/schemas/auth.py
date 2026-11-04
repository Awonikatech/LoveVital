import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORM, PHONE_RE


def _strong(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("Password must contain letters and numbers")
    return v


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(max_length=128)
    phone: str | None = None

    _pw = field_validator("password")(classmethod(lambda cls, v: _strong(v)))

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip().replace(" ", "")
        if not PHONE_RE.match(v):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return v[-10:]


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=128)

    _pw = field_validator("password")(classmethod(lambda cls, v: _strong(v)))


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(max_length=128)

    _pw = field_validator("new_password")(classmethod(lambda cls, v: _strong(v)))


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    phone: str | None
    is_active: bool
    email_verified_at: datetime | None
    roles: list[str]
    permissions: list[str]
    created_at: datetime


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip().replace(" ", "")
        if not PHONE_RE.match(v):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return v[-10:]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
