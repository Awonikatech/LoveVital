from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings


def utcnow() -> datetime:
    # Stored as naive UTC for MySQL DATETIME portability.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class IdMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


def make_engine(url: str):
    kwargs: dict = {"echo": settings.DB_ECHO, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url.endswith("sqlite://"):
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
    else:
        kwargs.update(pool_size=settings.DB_POOL_SIZE, max_overflow=20, pool_pre_ping=True, pool_recycle=1800)
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return eng


engine = make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
