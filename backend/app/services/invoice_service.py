"""GST tax invoices and packing slips rendered as PDF (ReportLab)."""
import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.models import Order
from app.services.common import get_setting
from app.services.order_service import STATUS_LABELS

GOLD = colors.HexColor("#A67C2E")
INK = colors.HexColor("#2B2118")
MUTED = colors.HexColor("#7A6A58")
IVORY = colors.HexColor("#FBF7EF")

_FONT, _BOLD, RUPEE = "Helvetica", "Helvetica-Bold", "Rs. "
for reg, bold in [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]:
    if os.path.exists(reg) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("DejaVu", reg))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
        _FONT, _BOLD, RUPEE = "DejaVu", "DejaVu-Bold", "₹"


def _styles():
    return {
        "brand": ParagraphStyle("brand", fontName=_BOLD, fontSize=20, textColor=GOLD, leading=24),
        "h": ParagraphStyle("h", fontName=_BOLD, fontSize=11, textColor=INK, leading=14),
        "p": ParagraphStyle("p", fontName=_FONT, fontSize=8.5, textColor=INK, leading=11.5),
        "m": ParagraphStyle("m", fontName=_FONT, fontSize=8, textColor=MUTED, leading=10.5),
        "r": ParagraphStyle("r", fontName=_FONT, fontSize=8.5, textColor=INK, leading=11.5, alignment=2),
    }


def _addr(a) -> str:
    if not a:
        return "-"
    parts = [f"<b>{a.full_name}</b>", a.line1, a.line2, a.landmark, f"{a.city}, {a.state} {a.pin_code}", f"Phone: {a.phone}"]
    if getattr(a, "gstin", None):
        parts.append(f"GSTIN: {a.gstin}")
    return "<br/>".join(p for p in parts if p)


def _money(v) -> str:
    return f"−{RUPEE}{abs(v):,.2f}" if v < 0 else f"{RUPEE}{v:,.2f}"


def _header(db: Session, order: Order, title: str, st) -> list:
    store = get_setting(db, "store_name", "LoveVital")
    addr = get_setting(db, "store_address", "")
    gstin = get_setting(db, "gstin", "")
    left = Paragraph(f"{store}<br/><font size=8 color='#7A6A58'>{addr}<br/>GSTIN: {gstin}</font>", st["brand"])
    right = Paragraph(
        f"<b>{title}</b><br/>Order No: {order.order_number}<br/>Date: {order.placed_at:%d %b %Y}<br/>"
        f"Payment: {order.payment_method.upper()} · {order.payment_status.replace('_', ' ').title()}<br/>"
        f"Status: {STATUS_LABELS.get(order.status, order.status)}",
        st["r"],
    )
    t = Table([[left, right]], colWidths=[105 * mm, 75 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, GOLD), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    addr_t = Table(
        [[Paragraph("<b>Bill To</b>", st["h"]), Paragraph("<b>Ship To</b>", st["h"])],
         [Paragraph(_addr(order.address("billing")), st["p"]), Paragraph(_addr(order.address("shipping")), st["p"])]],
        colWidths=[90 * mm, 90 * mm],
    )
    addr_t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    return [t, Spacer(1, 6), addr_t, Spacer(1, 8)]


def invoice_pdf(db: Session, order: Order) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Invoice {order.order_number}")
    story = _header(db, order, "TAX INVOICE", st)
    rows = [["#", "Item", "HSN", "Qty", "MRP", "Price", "Discount", "GST", "Amount"]]
    for i, it in enumerate(order.items, 1):
        rows.append([
            str(i), Paragraph(f"{it.product_name}<br/><font color='#7A6A58' size=7>{it.variant_name or ''} · SKU {it.sku}</font>", st["p"]),
            it.hsn_code or "-", str(it.quantity), _money(it.unit_mrp), _money(it.unit_price), _money(it.discount_amount),
            f"{it.tax_rate:.0f}%\n{_money(it.tax_amount)}", _money(it.line_total),
        ])
    t = Table(rows, colWidths=[7 * mm, 55 * mm, 13 * mm, 9 * mm, 19 * mm, 19 * mm, 19 * mm, 18 * mm, 21 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), _BOLD), ("FONTNAME", (0, 1), (-1, -1), _FONT), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), IVORY), ("TEXTCOLOR", (0, 0), (-1, 0), GOLD), ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E8DCC6")),
    ]))
    story += [t, Spacer(1, 8)]
    totals = [
        ("Total MRP", order.subtotal_mrp), ("Item discount", -order.item_discount_total),
        ("Offer discount", -order.promotion_discount),
        (f"Coupon ({order.coupon_code})" if order.coupon_code else "Coupon", -order.coupon_discount),
        ("Shipping", order.shipping_charge), ("COD fee", order.cod_charge),
    ]
    trows = [[k, _money(v)] for k, v in totals if v]
    trows.append(["Grand Total", _money(order.grand_total)])
    trows.append([f"Includes GST of", _money(order.tax_total)])
    if order.refunded_total:
        trows.append(["Refunded", _money(-order.refunded_total)])
    tt = Table(trows, colWidths=[45 * mm, 30 * mm], hAlign="RIGHT")
    tt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FONT), ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, len(trows) - 2 - (1 if order.refunded_total else 0)), (-1, len(trows) - 2 - (1 if order.refunded_total else 0)), _BOLD),
        ("LINEABOVE", (0, len(trows) - 2 - (1 if order.refunded_total else 0)), (-1, len(trows) - 2 - (1 if order.refunded_total else 0)), 0.8, GOLD),
    ]))
    story += [tt, Spacer(1, 14),
              Paragraph("All prices are inclusive of GST. This is a computer-generated invoice and does not require a signature. "
                        "Demo store — not a valid tax document.", st["m"])]
    doc.build(story)
    return buf.getvalue()


def packing_slip_pdf(db: Session, order: Order) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Packing slip {order.order_number}")
    story = _header(db, order, "PACKING SLIP", st)
    rows = [["✓", "SKU", "Item", "Variant", "Qty"]]
    for it in order.items:
        rows.append(["☐", it.sku, Paragraph(it.product_name, st["p"]), it.variant_name or "-", str(it.quantity)])
    t = Table(rows, colWidths=[10 * mm, 35 * mm, 80 * mm, 40 * mm, 15 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), _BOLD), ("FONTNAME", (0, 1), (-1, -1), _FONT), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), IVORY), ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E8DCC6")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [t, Spacer(1, 10)]
    ship = order.shipments[-1] if order.shipments else None
    story.append(Paragraph(
        f"Shipping method: {order.shipping_method_name or '-'}<br/>Courier: {ship.courier_name if ship else '-'} · AWB: {ship.tracking_number if ship else '-'}<br/>"
        f"{'COLLECT CASH: ' + _money(order.grand_total) if order.payment_method == 'cod' and order.payment_status != 'paid' else 'PREPAID — do not collect cash'}<br/>"
        f"Customer note: {order.customer_note or '-'}", st["p"]))
    doc.build(story)
    return buf.getvalue()
