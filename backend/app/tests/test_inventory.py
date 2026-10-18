"""Inventory reservations, expiry sweeps, manual adjustments and (on MySQL/MariaDB) concurrent reservation."""
import os
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import utcnow
from app.models import InventoryMovement, InventoryReservation, Order
from app.services import inventory_service
from app.tests.conftest import inv, place_order, start_payment

GLD = "JW-EAR-001-GLD"


def _order(db, oid) -> Order:
    db.expire_all()
    return db.get(Order, oid)


def _expire_reservations(db, order_id: int) -> None:
    db.execute(update(InventoryReservation).where(InventoryReservation.order_id == order_id)
               .values(expires_at=utcnow() - timedelta(minutes=1)))
    db.commit()


def test_sweep_releases_expired_reservation_but_keeps_order_payable(client, db, catalog, users, cust_h):
    vid = catalog.vid(GLD)
    order = place_order(client, cust_h, [(vid, 3)])
    assert inv(db, vid).quantity_reserved == 3
    _expire_reservations(db, order["id"])

    assert inventory_service.sweep_expired(db) == 1
    i = inv(db, vid)
    assert (i.quantity_on_hand, i.quantity_reserved) == (10, 0)
    o = _order(db, order["id"])
    assert o.status == "payment_pending" and o.payment_status == "pending"
    resv = db.scalar(select(InventoryReservation).where(InventoryReservation.order_id == o.id))
    assert resv.status == "released" and resv.release_reason == "expired"

    # a second sweep is a no-op
    assert inventory_service.sweep_expired(db) == 0
    # retrying payment re-reserves the stock
    start_payment(client, cust_h, order)
    assert inv(db, vid).quantity_reserved == 3


def test_sweep_ignores_unexpired_and_cod_orders(client, db, catalog, users, cust_h):
    vid = catalog.vid(GLD)
    place_order(client, cust_h, [(vid, 1)])
    cod = place_order(client, cust_h, [(vid, 1)], payment_method="cod")
    _expire_reservations(db, cod["id"])  # committed reservations are not "active" anyway
    assert inventory_service.sweep_expired(db) == 0
    i = inv(db, vid)
    assert (i.quantity_on_hand, i.quantity_reserved) == (9, 1)


def test_stale_unpaid_order_is_cancelled_by_sweep(client, db, catalog, users, cust_h):
    from app.models import Coupon

    db.add(Coupon(code="STALE5", discount_type="percent", value=Decimal("5")))
    db.commit()
    vid = catalog.vid(GLD)
    order = place_order(client, cust_h, [(vid, 2)], coupon_code="STALE5")
    o = _order(db, order["id"])
    o.placed_at = utcnow() - timedelta(hours=settings.PENDING_ORDER_TTL_HOURS + 1)
    db.commit()

    assert inventory_service.sweep_expired(db) == 1
    o = _order(db, order["id"])
    assert o.status == "cancelled"
    assert o.payment_status == "cancelled"
    assert o.cancellation_reason == "Payment not completed"
    assert o.history[-1].actor_type == "system"
    assert inv(db, vid).quantity_reserved == 0
    assert db.scalar(select(Coupon).where(Coupon.code == "STALE5")).times_used == 0


def test_recent_unpaid_order_not_cancelled(client, db, catalog, users, cust_h):
    order = place_order(client, cust_h, [(catalog.vid(GLD), 1)])
    o = _order(db, order["id"])
    o.placed_at = utcnow() - timedelta(hours=settings.PENDING_ORDER_TTL_HOURS - 1)
    db.commit()
    inventory_service.sweep_expired(db)
    assert _order(db, order["id"]).status == "payment_pending"


def test_admin_adjust_below_reserved_rejected(client, db, catalog, users, cust_h, admin_h):
    vid = catalog.vid(GLD)
    place_order(client, cust_h, [(vid, 4)])
    r = client.post("/api/v1/admin/inventory/adjust", json={"variant_id": vid, "delta": -7, "movement_type": "damage"}, headers=admin_h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "below_reserved"
    assert inv(db, vid).quantity_on_hand == 10

    ok = client.post("/api/v1/admin/inventory/adjust", json={"variant_id": vid, "delta": -6, "movement_type": "damage", "note": "Broken"},
                     headers=admin_h)
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"variant_id": vid, "on_hand": 4, "reserved": 4, "available": 0, "low_stock_threshold": 2}


def test_movements_record_balance_after(client, db, catalog, users, admin_h):
    vid = catalog.vid("AP-KRT-001-S")
    for delta, mtype in ((5, "restock"), (-3, "damage"), (2, "adjustment")):
        r = client.post("/api/v1/admin/inventory/adjust", json={"variant_id": vid, "delta": delta, "movement_type": mtype}, headers=admin_h)
        assert r.status_code == 200
    db.expire_all()
    mv = db.scalars(select(InventoryMovement).where(InventoryMovement.variant_id == vid).order_by(InventoryMovement.id)).all()
    assert [(m.movement_type, m.quantity, m.balance_after) for m in mv] == [
        ("initial", 20, 20), ("restock", 5, 25), ("damage", -3, 22), ("adjustment", 2, 24)]
    assert mv[1].created_by_id == users.admin.id

    listing = client.get("/api/v1/admin/inventory/movements", params={"variant_id": vid}, headers=admin_h).json()
    assert [m["balance_after"] for m in listing["items"]] == [24, 22, 25, 20]
    assert listing["items"][0]["by"] == "Store Admin"


def test_adjust_rejects_invalid_movement_type(db, catalog):
    from app.core.errors import ValidationFailed

    with pytest.raises(ValidationFailed):
        inventory_service.adjust(db, catalog.vid(GLD), 1, "sale", None, None)
    db.rollback()


def test_reserve_insufficient_stock_raises_with_details(client, db, catalog, users, cust_h):
    vid = catalog.vid("JW-EAR-001-RED")
    order = place_order(client, cust_h, [(vid, 1)])
    o = _order(db, order["id"])
    with pytest.raises(inventory_service.InsufficientStock) as exc:
        inventory_service.reserve(db, o, {vid: 3})
    db.rollback()
    assert exc.value.details[0]["available"] == 2 and exc.value.details[0]["requested"] == 3
    assert inv(db, vid).quantity_reserved == 1


# ----------------------------------------------------------------------------- real concurrency (MySQL/MariaDB)
@pytest.mark.skipif(not os.environ.get("TEST_MYSQL_URL"), reason="TEST_MYSQL_URL not set (needs a MySQL/MariaDB server)")
def test_concurrent_reservations_never_oversell_on_mysql():
    """12 threads race to reserve 1 unit each of a variant with 5 in stock, each in its own transaction.
    SELECT ... FOR UPDATE must serialise them: exactly 5 succeed, the rest get InsufficientStock."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base
    from app.models import Category, Inventory, Product, ProductVariant

    url = os.environ["TEST_MYSQL_URL"]
    eng = create_engine(url, pool_size=15, max_overflow=5, pool_pre_ping=True)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    threads_n, stock = 12, 5
    try:
        with Session() as s:
            cat = Category(slug="race", name="Race")
            s.add(cat)
            s.flush()
            p = Product(sku="RACE-1", slug="race-1", name="Race Item", product_type="jewellery", category_id=cat.id, status="active")
            s.add(p)
            s.flush()
            v = ProductVariant(product_id=p.id, sku="RACE-1", name="Only", mrp=Decimal("100"), sale_price=Decimal("100"))
            s.add(v)
            s.flush()
            s.add(Inventory(variant_id=v.id, quantity_on_hand=stock, quantity_reserved=0))
            order_ids = []
            for i in range(threads_n):
                o = Order(order_number=f"RACE{i:04d}", email=f"r{i}@example.com", status="payment_pending", payment_method="razorpay",
                          subtotal_mrp=Decimal("100"), subtotal=Decimal("100"), grand_total=Decimal("100"))
                s.add(o)
                s.flush()
                order_ids.append(o.id)
            s.commit()
            vid = v.id

        barrier = threading.Barrier(threads_n)
        results: list[str] = []
        lock = threading.Lock()

        def worker(oid: int) -> None:
            with Session() as s:
                order = s.get(Order, oid)
                s.commit()  # end the read transaction so every worker starts its locking transaction together
                barrier.wait(timeout=30)
                try:
                    inventory_service.reserve(s, order, {vid: 1})
                    s.commit()
                    outcome = "ok"
                except inventory_service.InsufficientStock:
                    s.rollback()
                    outcome = "insufficient"
                except Exception as e:  # pragma: no cover - surfaced in the assertion below
                    s.rollback()
                    outcome = f"error: {type(e).__name__}: {e}"
            with lock:
                results.append(outcome)

        threads = [threading.Thread(target=worker, args=(oid,)) for oid in order_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert len(results) == threads_n, results
        assert results.count("ok") == stock, results
        assert results.count("insufficient") == threads_n - stock, results
        with Session() as s:
            row = s.scalar(select(Inventory).where(Inventory.variant_id == vid))
            assert row.quantity_reserved == stock
            assert row.quantity_on_hand == stock
            active = s.scalars(select(InventoryReservation).where(InventoryReservation.status == "active")).all()
            assert len(active) == stock
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()
