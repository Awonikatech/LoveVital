from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, IdMixin, TimestampMixin, utcnow

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(IdMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    permissions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))  # null for guest-only records
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    support_notes: Mapped[str | None] = mapped_column(Text)
    disabled_reason: Mapped[str | None] = mapped_column(String(255))

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")
    addresses: Mapped[list["Address"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def role_names(self) -> list[str]:
        return [r.name for r in self.roles]

    @property
    def permissions(self) -> set[str]:
        perms: set[str] = set()
        for r in self.roles:
            perms.update(r.permissions or [])
        return perms

    def has_permission(self, perm: str) -> bool:
        p = self.permissions
        return "*" in p or perm in p or f"{perm.split(':')[0]}:*" in p

    @property
    def is_staff(self) -> bool:
        return any(r.name in ("admin", "staff") for r in self.roles)


class RefreshToken(IdMixin, Base):
    __tablename__ = "refresh_tokens"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    family_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AuthToken(IdMixin, Base):
    """Single-use tokens for email verification and password reset (stored hashed)."""

    __tablename__ = "auth_tokens"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)  # verify_email | reset_password
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Address(IdMixin, TimestampMixin, Base):
    __tablename__ = "addresses"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(50))
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255))
    landmark: Mapped[str | None] = mapped_column(String(150))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    pin_code: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    is_default_shipping: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default_billing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="addresses")


class NewsletterSubscriber(IdMixin, TimestampMixin, Base):
    __tablename__ = "newsletter_subscribers"
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="subscribed", nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Notification(IdMixin, Base):
    __tablename__ = "notifications"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    template: Mapped[str] = mapped_column(String(60), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(50), index=True)
    changes: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)


class StoreSetting(IdMixin, TimestampMixin, Base):
    __tablename__ = "store_settings"
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(String(255))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CmsPage(IdMixin, TimestampMixin, Base):
    __tablename__ = "cms_pages"
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # markdown
    seo_title: Mapped[str | None] = mapped_column(String(200))
    seo_description: Mapped[str | None] = mapped_column(String(300))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Banner(IdMixin, TimestampMixin, Base):
    __tablename__ = "banners"
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300))
    eyebrow: Mapped[str | None] = mapped_column(String(80))
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    cta_text: Mapped[str | None] = mapped_column(String(50))
    cta_link: Mapped[str | None] = mapped_column(String(300))
    placement: Mapped[str] = mapped_column(String(20), default="hero", nullable=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("title", "placement", name="uq_banner_title_placement"),)
