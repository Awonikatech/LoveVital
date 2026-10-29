from fastapi import APIRouter

from app.api.v1.admin import management, orders, payments, products, taxonomy

router = APIRouter(prefix="/admin")
router.include_router(management.router)
router.include_router(products.router)
router.include_router(taxonomy.router)
router.include_router(orders.router)
router.include_router(payments.router)
