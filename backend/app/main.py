import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1 import account, auth, cart, catalog, content, orders
from app.api.v1.admin import router as admin_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging

configure_logging()
log = logging.getLogger("app")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def _reservation_sweeper(stop: asyncio.Event) -> None:
    from app.services.inventory_service import sweep_expired

    while not stop.is_set():
        try:
            db = SessionLocal()
            try:
                n = await asyncio.to_thread(sweep_expired, db)
                if n:
                    log.info("Released %s expired inventory reservation(s)", n)
            finally:
                db.close()
        except Exception:  # keep the loop alive
            log.exception("reservation sweep failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.RESERVATION_SWEEP_SECONDS)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    task = None
    if settings.ENVIRONMENT != "test":
        task = asyncio.create_task(_reservation_sweeper(stop))
    log.info("%s API started (env=%s, payments=%s)", settings.APP_NAME, settings.ENVIRONMENT, settings.RAZORPAY_MODE)
    yield
    stop.set()
    if task:
        await task


app = FastAPI(
    title=f"{settings.APP_NAME} Commerce API",
    version="1.0.0",
    description="Jewellery & apparel e-commerce platform. Prices are Decimal strings in INR (tax-inclusive). "
                "Authenticate with `Authorization: Bearer <access_token>`; guests use the `X-Cart-Token` header.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

register_error_handlers(app)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Cart-Token", "X-CSRF-Token", "Idempotency-Key"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.COOKIE_SECURE:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith(settings.API_V1_PREFIX) and request.method == "GET" and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


for r in (auth.router, catalog.router, content.router, cart.router, orders.router, account.router, admin_router):
    app.include_router(r, prefix=settings.API_V1_PREFIX)

os.makedirs(os.path.join(BASE_DIR, settings.MEDIA_DIR, "uploads"), exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/media", StaticFiles(directory=os.path.join(BASE_DIR, settings.MEDIA_DIR)), name="media")


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


@app.get("/health/ready", tags=["ops"])
def ready():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    finally:
        db.close()
