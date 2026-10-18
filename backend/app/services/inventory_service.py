"""Inventory with reservations.

available = quantity_on_hand - quantity_reserved

* reserve()  — at order creation. Locks inventory rows with SELECT ... FOR UPDATE in ascending
               variant-id order (consistent lock order prevents deadlocks), checks availability,
               increments `quantity_reserved` and writes an `inventory_reservations` row that expires
               after RESERVATION_TTL_MINUTES.
* commit()   — on payment capture / COD confirmation: on_hand -= qty, reserved -= qty, SALE movement.
* release()  — on payment failure, cancellation before commit, or expiry: reserved -= qty.
* restock()  — on cancellation after commit or on accepted returns: on_hand += qty.
Every on-hand change writes an `inventory_movements` row with the resulting balance."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import Inventory, InventoryMovement, InventoryReservation, Order, Product, ProductVariant, User


class InsufficientStock(Conflict):
    code = "insufficient_stock"


def _lock_inventory(db: Session, variant_ids: list[int]) -> dict[int, Inventory]:
    rows = db.scalars(
        select(Inventory).where(Inventory.variant_id.in_(sorted(set(variant_ids)))).order_by(Inventory.variant_id).with_for_update()
    ).all()
    return {r.variant_id: r for r in rows}


def _movement(db: Session, inv: Inventory, mtype: str, qty: int, ref_type: str | None, ref_id, note: str | None, user: User | None):
    db.add(
        InventoryMovement(
            variant_id=inv.variant_id, movement_type=mtype, quantity=qty, balance_after=inv.quantity_on_hand,
            reference_type=ref_type, reference_id=str(ref_id) if ref_id is not None else None, note=note,
            created_by_id=user.id if user else None,
        )
    )


def reserve(db: Session, order: Order, wanted: dict[int, int], ttl_minutes: int | None = None) -> None:
    invs = _lock_inventory(db, list(wanted))
    problems = []
    for vid, qty in sorted(wanted.items()):
        inv = invs.get(vid)
        avail = inv.available if inv else 0
        if avail < qty:
            v = db.get(ProductVariant, vid)
            problems.append({"variant_id": vid, "sku": v.sku if v else None, "requested": qty, "available": avail,
                             "name": v.product.name if v else None})
    if problems:
        names = ", ".join(f"{p['name']} (only {p['available']} left)" for p in problems)
        raise InsufficientStock(f"Not enough stock for: {names}", details=problems)
    expires = utcnow() + timedelta(minutes=ttl_minutes or settings.RESERVATION_TTL_MINUTES)
    for vid, qty in wanted.items():
        invs[vid].quantity_reserved += qty
        db.add(InventoryReservation(variant_id=vid, order_id=order.id, quantity=qty, status="active", expires_at=expires))
    db.flush()


def commit(db: Session, order: Order) -> bool:
    """Convert active reservations into sales. If reservations had expired/been released (late
    payment), re-reserve atomically; returns False if stock is no longer available."""
    resv = db.scalars(
        select(InventoryReservation).where(InventoryReservation.order_id == order.id).with_for_update()
    ).all()
    if resv and all(r.status == "committed" for r in resv):
        return True
    active = [r for r in resv if r.status == "active"]
    if len(active) != len(resv) or not resv:
        # Late payment after expiry: try to grab the stock again.
        wanted: dict[int, int] = {}
        for it in order.items:
            if it.variant_id:
                wanted[it.variant_id] = wanted.get(it.variant_id, 0) + it.quantity
        invs = _lock_inventory(db, list(wanted))
        if any((invs.get(v).available if invs.get(v) else 0) < q for v, q in wanted.items()):
            return False
        for r in resv:
            if r.status != "active":
                db.delete(r)
        db.flush()
        reserve(db, order, wanted)
        active = db.scalars(select(InventoryReservation).where(InventoryReservation.order_id == order.id)).all()
    invs = _lock_inventory(db, [r.variant_id for r in active])
    for r in active:
        inv = invs[r.variant_id]
        inv.quantity_reserved = max(0, inv.quantity_reserved - r.quantity)
        inv.quantity_on_hand -= r.quantity
        if inv.quantity_on_hand < 0:
            raise InsufficientStock("Inventory became negative; aborting")
        r.status = "committed"
        _movement(db, inv, "sale", -r.quantity, "order", order.order_number, None, None)
    # popularity counters
    for it in order.items:
        if it.product_id:
            p = db.get(Product, it.product_id)
            if p:
                p.sold_count += it.quantity
    db.flush()
    return True


def release(db: Session, order: Order, reason: str) -> int:
    resv = db.scalars(
        select(InventoryReservation).where(InventoryReservation.order_id == order.id, InventoryReservation.status == "active").with_for_update()
    ).all()
    if not resv:
        return 0
    invs = _lock_inventory(db, [r.variant_id for r in resv])
    now = utcnow()
    for r in resv:
        inv = invs.get(r.variant_id)
        if inv:
            inv.quantity_reserved = max(0, inv.quantity_reserved - r.quantity)
        r.status, r.released_at, r.release_reason = "released", now, reason
    db.flush()
    return len(resv)


def restock_order(db: Session, order: Order, mtype: str, user: User | None, quantities: dict[int, int] | None = None, note: str | None = None) -> None:
    """Return committed stock to on-hand (cancellation after commit, or accepted return)."""
    wanted: dict[int, int] = {}
    for it in order.items:
        if not it.variant_id:
            continue
        qty = quantities.get(it.id, 0) if quantities is not None else it.quantity
        if qty > 0:
            wanted[it.variant_id] = wanted.get(it.variant_id, 0) + qty
    invs = _lock_inventory(db, list(wanted))
    for vid, qty in wanted.items():
        inv = invs.get(vid)
        if inv:
            inv.quantity_on_hand += qty
            _movement(db, inv, mtype, qty, "order", order.order_number, note, user)
    db.flush()


def order_is_committed(db: Session, order: Order) -> bool:
    return db.scalar(
        select(InventoryReservation.id).where(InventoryReservation.order_id == order.id, InventoryReservation.status == "committed").limit(1)
    ) is not None


def adjust(db: Session, variant_id: int, delta: int, mtype: str, note: str | None, user: User | None,
           low_stock_threshold: int | None = None) -> Inventory:
    if mtype not in {"restock", "adjustment", "damage", "return", "initial"}:
        raise ValidationFailed("Invalid movement type")
    invs = _lock_inventory(db, [variant_id])
    inv = invs.get(variant_id)
    if inv is None:
        if not db.get(ProductVariant, variant_id):
            raise NotFound("Variant not found")
        inv = Inventory(variant_id=variant_id, quantity_on_hand=0, quantity_reserved=0)
        db.add(inv)
        db.flush()
    if inv.quantity_on_hand + delta < inv.quantity_reserved:
        raise ValidationFailed(
            f"Cannot reduce below reserved quantity ({inv.quantity_reserved} reserved for pending orders)",
            code="below_reserved",
        )
    inv.quantity_on_hand += delta
    if low_stock_threshold is not None:
        inv.low_stock_threshold = low_stock_threshold
    if delta:
        _movement(db, inv, mtype, delta, "manual", None, note, user)
    db.flush()
    return inv


def sweep_expired(db: Session) -> int:
    """Release expired reservations and cancel their unpaid orders. Safe to run concurrently."""
    from app.services import order_service

    now = utcnow()
    order_ids = db.scalars(
        select(InventoryReservation.order_id)
        .where(InventoryReservation.status == "active", InventoryReservation.expires_at < now)
        .distinct()
    ).all()
    n = 0
    for oid in order_ids:
        order = db.scalar(select(Order).where(Order.id == oid).with_for_update())
        if not order or order.payment_status in ("paid",) or order.payment_method == "cod":
            continue
        # Stock goes back on sale; the order stays payable and re-reserves stock if the customer retries.
        release(db, order, "expired")
        n += 1
    # Orders whose payment failed (stock already released) stay retryable for PENDING_ORDER_TTL_HOURS, then close.
    cutoff = now - timedelta(hours=settings.PENDING_ORDER_TTL_HOURS)
    stale = db.scalars(select(Order).where(Order.status == "payment_pending", Order.placed_at < cutoff).with_for_update()).all()
    for order in stale:
        release(db, order, "expired")
        order_service.transition(db, order, "cancelled", actor=None, note="Unpaid order closed automatically",
                                 actor_type="system", skip_side_effects=True)
        order.cancellation_reason = "Payment not completed"
        order.payment_status = "cancelled" if order.payment_status in ("pending", "failed") else order.payment_status
        order_service.reverse_coupon(db, order)
        n += 1
    db.commit()
    return n
