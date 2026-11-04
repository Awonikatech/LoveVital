import re
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

T = TypeVar("T")

# Decimals are serialised as strings ("499.00") so no precision is lost in JSON.
MoneyStr = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="json")]

PIN_RE = re.compile(r"^[1-9][0-9]{5}$")
PHONE_RE = re.compile(r"^(\+91[\-\s]?)?[6-9]\d{9}$")

INDIAN_STATES = [
    "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh",
    "Chhattisgarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry",
    "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal",
]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Message(BaseModel):
    message: str


class AddressIn(BaseModel):
    label: str | None = Field(default=None, max_length=50)
    full_name: str = Field(min_length=2, max_length=150)
    phone: str
    line1: str = Field(min_length=3, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    landmark: str | None = Field(default=None, max_length=150)
    city: str = Field(min_length=2, max_length=100)
    state: str
    pin_code: str
    country: str = "IN"
    is_default_shipping: bool = False
    is_default_billing: bool = False

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not PHONE_RE.match(v):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return v[-10:]

    @field_validator("pin_code")
    @classmethod
    def _pin(cls, v: str) -> str:
        v = v.strip()
        if not PIN_RE.match(v):
            raise ValueError("Enter a valid 6-digit PIN code")
        return v

    @field_validator("state")
    @classmethod
    def _state(cls, v: str) -> str:
        match = next((s for s in INDIAN_STATES if s.lower() == v.strip().lower()), None)
        if not match:
            raise ValueError("Select a valid Indian state / UT")
        return match

    @field_validator("country")
    @classmethod
    def _country(cls, v: str) -> str:
        if v.upper() != "IN":
            raise ValueError("We currently ship within India only")
        return "IN"


class AddressOut(ORM):
    id: int
    label: str | None
    full_name: str
    phone: str
    line1: str
    line2: str | None
    landmark: str | None
    city: str
    state: str
    pin_code: str
    country: str
    is_default_shipping: bool
    is_default_billing: bool
