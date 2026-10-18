"""Application settings, loaded exclusively from environment variables / .env."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "LoveVital"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Database ---
    DATABASE_URL: str = "mysql+pymysql://aurum:aurum_dev_pw@127.0.0.1:3306/aurum?charset=utf8mb4"
    DB_POOL_SIZE: int = 10
    DB_ECHO: bool = False

    # --- Security ---
    SECRET_KEY: str = Field(default="dev-only-change-me-please-0123456789abcdef", min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    COOKIE_SECURE: bool = False  # MUST be true in production (HTTPS)
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    RATE_LIMIT_ENABLED: bool = True

    # --- Razorpay ---
    # "mock" runs a local, signature-compatible simulator: no network, no credentials.
    RAZORPAY_MODE: Literal["mock", "test", "live"] = "mock"
    RAZORPAY_KEY_ID: str = "rzp_mock_key"
    RAZORPAY_KEY_SECRET: str = "mock_secret_change_me"
    RAZORPAY_WEBHOOK_SECRET: str = "mock_webhook_secret"
    PAYMENT_CURRENCY: str = "INR"

    # --- Commerce ---
    RESERVATION_TTL_MINUTES: int = 15
    RESERVATION_SWEEP_SECONDS: int = 60
    PENDING_ORDER_TTL_HOURS: int = 24  # unpaid orders (e.g. after a failed payment) can be retried for this long
    ORDER_NUMBER_PREFIX: str = "SWK"

    # --- Email ---
    EMAIL_BACKEND: Literal["console", "smtp"] = "console"
    EMAIL_FROM: str = "LoveVital <janviawadhesh@gmail.com>"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True

    # --- Shipping ---
    SHIPPING_PROVIDER: Literal["mock"] = "mock"

    # --- Uploads ---
    MEDIA_DIR: str = "media"
    MAX_UPLOAD_MB: int = 5

    # --- Seed (development only) ---
    SEED_ADMIN_EMAIL: str = "admin@lovevital.example.com"
    SEED_ADMIN_PASSWORD: str = "Admin@12345"
    SEED_STAFF_EMAIL: str = "staff@lovevital.example.com"
    SEED_STAFF_PASSWORD: str = "Staff@12345"
    SEED_CUSTOMER_EMAIL: str = "priya@example.com"
    SEED_CUSTOMER_PASSWORD: str = "Customer@123"

    @field_validator("DATABASE_URL")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production:
        insecure = []
        if s.SECRET_KEY.startswith("dev-only"):
            insecure.append("SECRET_KEY")
        if not s.COOKIE_SECURE:
            insecure.append("COOKIE_SECURE")
        if s.RAZORPAY_MODE == "mock":
            insecure.append("RAZORPAY_MODE")
        if insecure:
            raise RuntimeError(f"Refusing to start in production with insecure settings: {', '.join(insecure)}")
    return s


settings = get_settings()
