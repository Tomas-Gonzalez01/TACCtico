from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from budget import ars, quantity_label


def create_pdf(orders, issued_at: datetime):
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=34, bottomMargin=44,
        title="TACCtico - Presupuesto estimado de compra",
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("Detail", parent=styles["Normal"], fontSize=8, leading=11)
    muted = "#425C56"
    accent = colors.HexColor("#174A3A")
    story = [
        Paragraph("TACCtico", styles["Heading1"]),
        Paragraph("Presupuesto estimado de compra", styles["Title"]),
        Paragraph(
            f"Emitido el {issued_at:%d/%m/%Y %H:%M} · Moneda ARS · Fuente Mercado Libre Argentina",
            small,
        ),
        Spacer(1, 10),
    ]
    complete = all(order.complete for order in orders)
    known = sum(order.known for order in orders)
    story.append(Paragraph(
        f"<b>{'Total estimado del pedido' if complete else 'Importe conocido'} · {ars(known)}</b>",
        styles["Heading2"],
    ))
    story.append(Paragraph("Precios de captura. Verificá disponibilidad, promociones y condiciones al cerrar el pedido.", small))

    for order in orders:
        rows = [[Paragraph(f"<b>{heading}</b>", small) for heading in (
            "Producto y categoría", "Pedido / entrega", "Precio publicado", "Mercadería e IVA",
        )]]
        for line in order.lines:
            quote = line.quote
            offer = quote.offer
            unit = offer.unit
            capture = offer.captured or "Sin dato"
            units = f"<br/>{quote.boxes * offer.units_per_pack} unidades" if offer.units_per_pack and unit == "kg" else ""
            rows.append([
                Paragraph(
                    f"<b>{escape(offer.product)}</b><br/>"
                    f"Categoría: {escape(offer.category or 'Sin confirmar')}<br/>"
                    f'<font color="{muted}">Captura: {escape(capture)}</font><br/>'
                    f'<link href={quoteattr(offer.url)} color="#174A3A">Abrir publicación</link>',
                    small,
                ),
                Paragraph(
                    f"Pedís {quantity_label(quote.required, unit)}<br/>"
                    f"Recibís {quantity_label(quote.received, unit)}<br/>"
                    f"{quote.boxes} presentación(es){units}<br/>"
                    f"Sobran {quantity_label(quote.surplus, unit)}",
                    small,
                ),
                Paragraph(
                    f"{ars(offer.price)} / presentación<br/>"
                    f"{ars(line.merchandise / quote.received)} / {unit}",
                    small,
                ),
                Paragraph(
                    f"<b>{ars(line.merchandise)}</b><br/>{escape(line.tax_label)}"
                    f"<br/>Con datos disponibles: {ars(line.known)}",
                    small,
                ),
            ])
        table = Table(rows, colWidths=[197, 106, 111, doc.width - 414], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2EEE9")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7F5")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([
            Paragraph(escape(order.supplier), styles["Heading2"]),
            table,
            KeepTogether([
                Spacer(1, 6),
                Paragraph(
                    f"Mercadería {ars(order.merchandise)} · IVA a sumar conocido {ars(order.added_vat)}"
                    f" · Envío {ars(order.shipping)}",
                    small,
                ),
                Paragraph(
                    f"<b>{'Total estimado' if order.complete else 'Importe conocido'} · {ars(order.known)}</b>",
                    small,
                ),
            ]),
        ])

    def footer(canvas, document):
        canvas.setFillColor(accent)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(36, 24, "TACCtico")
        canvas.drawRightString(A4[0] - 36, 24, f"Página {document.page}")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
