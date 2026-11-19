from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from budget import ars, quantity_label


INK = colors.HexColor("#173729")
GREEN = colors.HexColor("#176344")
MUTED = colors.HexColor("#526557")
LINE = colors.HexColor("#D9E1D5")
PALE = colors.HexColor("#F0F4EB")
LOGO = Path(__file__).with_name("static") / "logo-tacctico.png"


def charge_amount(amount, pending):
    if pending and not amount:
        return "Sin confirmar"
    if pending:
        return f"{ars(amount)} + pendiente"
    return ars(amount)


def capture_label(value):
    if not value:
        return "Captura sin fecha"
    try:
        captured = datetime.fromisoformat(value)
    except ValueError:
        return f"Captura {value}"
    if captured.tzinfo is not None:
        captured = captured.astimezone(timezone.utc)
        return f"Captura {captured:%d/%m/%Y %H:%M} UTC"
    return f"Captura {captured:%d/%m/%Y %H:%M}"


def money_paragraph(value, style, width):
    text = ars(value)
    font_size = min(style.fontSize, width / stringWidth(text, style.fontName, 1))
    fitted = ParagraphStyle("FittedMoney", parent=style, fontSize=font_size, leading=font_size * 1.3)
    return Paragraph(text, fitted)


def create_pdf(orders, issued_at: datetime):
    orders = tuple(orders)
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=126,
        bottomMargin=48,
        title="TACCtico - Presupuesto de compra",
        author="TACCtico",
        subject="Detalle de productos, IVA y envío para planificar compras",
    )
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=INK)
    detail = ParagraphStyle("Detail", parent=body, fontSize=7.8, leading=10.5, textColor=MUTED)
    numeric = ParagraphStyle("Numeric", parent=body, alignment=TA_RIGHT)
    unit_money = ParagraphStyle("UnitMoney", parent=numeric, fontName="Helvetica-Bold")
    numeric_detail = ParagraphStyle("NumericDetail", parent=detail, alignment=TA_RIGHT)
    amount = ParagraphStyle("Amount", parent=numeric, fontName="Helvetica-Bold", fontSize=10, leading=13)
    label = ParagraphStyle("Label", parent=detail, textColor=GREEN)
    total_note = ParagraphStyle("TotalNote", parent=label, alignment=TA_RIGHT)
    supplier = ParagraphStyle("Supplier", parent=body, fontName="Helvetica-Bold", fontSize=11, leading=14)
    grand = ParagraphStyle("Grand", parent=body, fontName="Helvetica-Bold", fontSize=25, leading=31)

    lines = [line for order in orders for line in order.lines]
    complete = all(order.complete for order in orders)
    merchandise = sum((order.merchandise for order in orders), Decimal(0))
    added_vat = sum((order.added_vat for order in orders), Decimal(0))
    shipping = sum((order.shipping or Decimal(0) for order in orders), Decimal(0))
    known = sum((order.known for order in orders), Decimal(0))
    tax_pending = any(line.tax_pending for line in lines)
    shipping_pending = any(order.shipping is None for order in orders)
    total_label = "Total estimado del pedido" if complete else "Importe conocido"

    breakdown = Table(
        [
            [Paragraph("Mercadería", detail), Paragraph(ars(merchandise), numeric)],
            [Paragraph("IVA a sumar", detail), Paragraph(charge_amount(added_vat, tax_pending), numeric)],
            [Paragraph("Envío", detail), Paragraph(charge_amount(shipping, shipping_pending), numeric)],
        ],
        colWidths=[82, 155],
    )
    breakdown.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    item_word = "insumo" if len(lines) == 1 else "insumos"
    supplier_word = "proveedor" if len(orders) == 1 else "proveedores"
    summary_rows = [
        [
            [
                Paragraph(total_label, label),
                money_paragraph(known, grand, doc.width - 293),
                Paragraph(f"{len(lines)} {item_word} · {len(orders)} {supplier_word} · Moneda ARS", detail),
            ],
            breakdown,
        ]
    ]
    if not complete:
        pending = []
        if tax_pending:
            pending.append("IVA")
        if shipping_pending:
            pending.append("envío")
        summary_rows.append(
            [
                Paragraph(
                    f"Pendiente de confirmar {' y '.join(pending)} para completar el total del pedido.",
                    detail,
                ),
                "",
            ]
        )
    summary = Table(summary_rows, colWidths=[doc.width - 265, 265])
    summary_style = [
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]
    if not complete:
        summary_style.extend(
            [
                ("SPAN", (0, 1), (-1, 1)),
                ("TOPPADDING", (0, 1), (-1, 1), 0),
            ]
        )
    summary.setStyle(TableStyle(summary_style))
    story = [summary, Spacer(1, 18)]
    column_widths = [doc.width - 314, 104, 103, 107]

    for order in orders:
        rows = [
            [Paragraph(escape(order.supplier), supplier), "", "", ""],
            [
                Paragraph(heading, label)
                for heading in (
                    "Producto",
                    "Pedido y entrega",
                    "Precio publicado",
                    "Importe",
                )
            ],
        ]
        for line in order.lines:
            quote = line.quote
            offer = quote.offer
            unit = "unidad" if offer.unit == "unidad" else offer.unit
            presentation = "presentación" if quote.boxes == 1 else "presentaciones"
            quantities = (
                f"Pedís <b>{quantity_label(quote.required, offer.unit)}</b><br/>"
                f"Recibís <b>{quantity_label(quote.received, offer.unit)}</b><br/>"
                f"{quote.boxes} {presentation}<br/>"
                f"Sobrante {quantity_label(quote.surplus, offer.unit)}"
            )
            if offer.units_per_pack and offer.unit == "kg":
                quantities += f"<br/>{quantity_label(quote.boxes * offer.units_per_pack, 'unidad')}"
            product = [
                Paragraph(f"<b>{escape(offer.product)}</b>", body),
                Paragraph(f"Categoría {escape(offer.category or 'Sin confirmar')}", detail),
                Paragraph(escape(capture_label(offer.captured)), detail),
                Paragraph(
                    f'<link href={quoteattr(offer.url)} color="#176344">Ver publicación en Mercado Libre</link>',
                    detail,
                ),
            ]
            rows.append(
                [
                    product,
                    Paragraph(quantities, body),
                    [
                        money_paragraph(offer.price, unit_money, column_widths[2] - 16),
                        Paragraph("por presentación", numeric_detail),
                        Spacer(1, 10),
                        money_paragraph(line.merchandise / quote.received, numeric, column_widths[2] - 16),
                        Paragraph(f"por {unit}", numeric_detail),
                    ],
                    [
                        money_paragraph(line.known, amount, column_widths[3] - 16),
                        Paragraph(escape(line.tax_label), numeric_detail),
                    ],
                ]
            )

        order_tax_pending = any(line.tax_pending for line in order.lines)
        rows.append(
            [
                Paragraph(
                    f"Mercadería {ars(order.merchandise)}<br/>"
                    f"IVA a sumar {charge_amount(order.added_vat, order_tax_pending)}<br/>"
                    f"Envío {ars(order.shipping)}",
                    detail,
                ),
                "",
                [
                    Paragraph(
                        "Total estimado del proveedor"
                        if order.complete
                        else "Importe conocido del proveedor",
                        total_note,
                    ),
                    Paragraph(ars(order.known), amount),
                ],
                "",
            ]
        )
        table = Table(rows, colWidths=column_widths, repeatRows=2, spaceAfter=12)
        table.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 0), (-1, 0)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, 0), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                    ("LINEBELOW", (0, 0), (-1, 0), 1.2, GREEN),
                    ("BACKGROUND", (0, 1), (-1, 1), PALE),
                    ("LINEBELOW", (0, 2), (-1, -2), 0.4, LINE),
                    ("SPAN", (0, -1), (1, -1)),
                    ("SPAN", (2, -1), (3, -1)),
                    ("BACKGROUND", (0, -1), (-1, -1), PALE),
                    ("NOSPLIT", (0, -2), (-1, -1)),
                ]
            )
        )
        story.append(table)

    story.append(
        Paragraph(
            "Precios de captura de Mercado Libre Argentina. Confirmá disponibilidad, "
            "promociones y condiciones con cada proveedor antes de comprar.",
            detail,
        )
    )

    def page_header_and_footer(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(3)
        canvas.line(36, height - 29, width - 36, height - 29)
        canvas.drawImage(str(LOGO), 36, height - 108, width=68, height=68, mask="auto")
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 19)
        canvas.drawString(118, height - 63, "Presupuesto de compra")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(118, height - 81, "Planificación de compras sin TACC")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - 36, height - 50, "Emitido el")
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawRightString(width - 36, height - 66, f"{issued_at:%d/%m/%Y}")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - 36, height - 81, f"{issued_at:%H:%M}")
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(36, 39, width - 36, 39)
        canvas.drawString(36, 25, "TACCtico · Presupuesto estimado · ARS")
        canvas.drawRightString(width - 36, 25, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_header_and_footer, onLaterPages=page_header_and_footer)
    return output.getvalue()
