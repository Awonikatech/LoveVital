"""Transactional emails. Messages are queued on the SQLAlchemy session and dispatched to a
background worker only *after* the transaction commits, so a rolled-back order never emails."""
import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import event
from sqlalchemy.orm import Session, object_session

from app.core.config import settings
from app.models import Order
from app.services.common import send_email_task

log = logging.getLogger("app.notify")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email")
SYNC_DISPATCH = False  # tests flip this to run inline


def _render(order: Order, template: str, extra: dict) -> tuple[str, str]:
    lines = "\n".join(f"  • {it.product_name} ({it.variant_name}) × {it.quantity} — ₹{it.line_total}" for it in order.items)
    link = f"{settings.FRONTEND_URL}/account/orders/{order.order_number}"
    if template == "order_confirmed":
        subject = f"Order confirmed — {order.order_number}"
        body = (f"Thank you for shopping with LoveVital!\n\nYour order {order.order_number} is confirmed.\n\n{lines}\n\n"
                f"Total paid: ₹{order.grand_total}\nEstimated delivery by {order.estimated_delivery_date:%d %b %Y}\n\nTrack your order: {link}")
    elif template == "order_shipped":
        subject = f"Your order {order.order_number} has shipped"
        s = order.shipments[-1] if order.shipments else None
        body = (f"Good news! Your order is on its way via {s.courier_name if s else 'our courier'}.\n"
                f"Tracking number: {s.tracking_number if s else '-'}\nTrack: {s.tracking_url if s else link}")
    elif template == "order_cancelled":
        subject = f"Order {order.order_number} cancelled"
        body = f"Your order {order.order_number} has been cancelled. Reason: {order.cancellation_reason or '-'}.\n\nDetails: {link}"
    elif template == "refund_initiated":
        subject = f"Refund initiated for {order.order_number}"
        body = (f"We've initiated a refund of ₹{extra.get('amount')} for order {order.order_number}. "
                "It usually reaches your original payment method within 5–7 business days.")
    elif template == "order_delivered":
        subject = f"Delivered: {order.order_number}"
        body = f"Your order has been delivered. We hope you love it! Leave a review: {link}"
    else:
        subject, body = f"Update on order {order.order_number}", f"Your order status: {order.status}. {link}"
    return subject, body


def queue_order_email(order: Order, template: str, extra: dict | None = None) -> None:
    subject, body = _render(order, template, extra or {})
    sess = object_session(order)
    item = (template, order.email, subject, body, order.user_id)
    if sess is None:
        _dispatch([item])
        return
    sess.info.setdefault("pending_emails", []).append(item)


def _dispatch(items: list[tuple]) -> None:
    for it in items:
        if SYNC_DISPATCH:
            send_email_task(*it)
        else:
            _executor.submit(send_email_task, *it)


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    items = session.info.pop("pending_emails", None)
    if items:
        _dispatch(items)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop("pending_emails", None)
