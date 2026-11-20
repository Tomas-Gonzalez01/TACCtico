from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from html import escape
from urllib.parse import urlsplit

import streamlit as st

from budget import BudgetLine, ars, budget_orders, money, parse_quantity, quantity_label, quantity_number
from budget_pdf import create_pdf
from purchase_engine import candidate_quotes


CART = "lista_compras"
LEGACY_PENDING = "reemplazo_lista"
NOTICE = "aviso_lista"
OFFER_REVISION = "revision_ofertas"
TAX_OPTIONS = {
    "pendiente": "Sin confirmar",
    "incluido": "Incluido en el precio",
    "neto": "Agregar IVA al precio neto",
}
OFFER_PICKER = st.components.v2.component(
    "tacctico_offers",
    html='<div class="offer-list"></div>',
    js=Path(__file__).with_name("offer_picker.js").read_text(encoding="utf-8"),
    css=Path(__file__).with_name("assets").joinpath("offers.css").read_text(encoding="utf-8"),
)


def acknowledge_offer_event():
    # A receipt forces the picker to render again even when its offers did not change.
    st.session_state[OFFER_REVISION] = st.session_state.get(OFFER_REVISION, 0) + 1


def choose_offer(quotes, *, key):
    if not quotes:
        return
    records = {}
    rows = []
    for quote in quotes:
        offer = quote.offer
        token = f"{offer.listing}/{offer.unit}/{quote.required}/{quote.boxes}"
        records[token] = quote
        presentation = "presentación" if quote.boxes == 1 else "presentaciones"
        measure = "kg" if offer.unit == "kg" else "unidad"
        rows.append(
            {
                "key": token,
                "title": offer.product,
                "seller": offer.supplier.name,
                "url": offer.url,
                "price": ars(quote.merchandise),
                "quantities": (
                    f"{quote.boxes} {presentation} · Recibís {quantity_label(quote.received, offer.unit)}"
                    f" · Sobrante {quantity_label(quote.surplus, offer.unit)}"
                ),
                "unit_price": (
                    f"{ars(quote.merchandise / quote.received)} por {measure}"
                    + (" · Precio atípico" if offer.outlier_price else "")
                ),
            }
        )
    st.markdown("**Ofertas comparables**")
    st.caption("Mercadería estimada para la cantidad pedida. Podés agregar con un botón o doble clic.")
    event = OFFER_PICKER(
        data={"offers": rows, "revision": st.session_state.get(OFFER_REVISION, 0)},
        key=key,
        on_add_offer_change=acknowledge_offer_event,
    )
    if event.add_offer in records:
        add_to_cart(records[event.add_offer])


def add_to_cart(quote):
    """Agrega una publicación; repetirla actualiza solo su cantidad, no otra oferta del insumo."""
    cart = st.session_state.setdefault(CART, {})
    # Reutilizar las claves antiguas conserva cantidades e IVA editados en sesiones abiertas.
    line_key = next(
        (key for key, line in cart.items() if line.offer.listing == quote.offer.listing),
        ("publicacion", quote.offer.listing),
    )
    current = cart.get(line_key)
    cart[line_key] = quote
    st.session_state.pop(LEGACY_PENDING, None)
    if current != quote:
        st.session_state[NOTICE] = (
            "Producto agregado a tu lista." if current is None else "Cantidad actualizada en tu lista."
        )


def restore_pending_offer():
    """Completa una adición que la versión anterior había dejado esperando reemplazo."""
    pending = st.session_state.pop(LEGACY_PENDING, None)
    if pending is not None:
        _, quote = pending
        add_to_cart(quote)


def remove_offer(line_key):
    removed = st.session_state[CART].pop(line_key, None)
    st.session_state.pop(LEGACY_PENDING, None)
    if removed is not None:
        st.session_state[NOTICE] = "Producto quitado de tu lista."


def show_notice():
    # Consume the action once so editing quantities, IVA or shipping cannot replay it.
    message = st.session_state.pop(NOTICE, None)
    if message:
        st.toast(message, icon=":material/check_circle:", duration="short")


def format_quantity_input(key, whole_units):
    try:
        value = parse_quantity(st.session_state[key], whole_units=whole_units)
    except ValueError:
        return
    st.session_state[key] = quantity_number(value)


def quantity_field(label, key, *, default=None, whole_units=False):
    if key not in st.session_state:
        st.session_state[key] = quantity_number(default) if default is not None else ""
    text = st.text_input(
        label,
        value=None,
        placeholder="Sin límite" if default is None else None,
        key=key,
        on_change=format_quantity_input,
        args=(key, whole_units),
    )
    if default is None and not text.strip():
        return None
    return parse_quantity(text, whole_units=whole_units)


def show_budget():
    restore_pending_offer()
    cart = st.session_state.setdefault(CART, {})
    st.subheader("Lista de compras", anchor="lista-de-compras")
    with st.container(key="avisos_lista"):
        show_notice()
    if not cart:
        st.info("Agregá una oferta desde la comparación para empezar tu presupuesto.")
        return

    st.caption(f"{len(cart)} {'producto' if len(cart) == 1 else 'productos'} en la lista")
    summary = st.container(key="resumen_presupuesto")
    lines = []
    for line_key, initial in cart.items():
        offer = initial.offer
        widget = f"{line_key}/{offer.listing}/{offer.unit}/{initial.required}/{initial.boxes}"
        with st.container(border=True):
            st.markdown(f"**{offer.product}**")
            st.caption(offer.supplier.name)
            try:
                required = quantity_field(
                    "Cantidad pedida (kg)" if offer.unit == "kg" else "Unidades pedidas",
                    f"pedido_{widget}",
                    default=initial.required,
                    whole_units=offer.unit == "unidad",
                )
            except ValueError as error:
                st.error(str(error))
                st.button("Quitar", key=f"quitar_{widget}", on_click=remove_offer, args=(line_key,))
                continue
            quote = (
                initial
                if required == initial.required
                else next(candidate_quotes(offer, required, offer.unit, published=True))
            )
            presentation = "presentación" if quote.boxes == 1 else "presentaciones"
            st.write(
                f"{quote.boxes} {presentation} · Recibís {quantity_label(quote.received, offer.unit)}"
                f" · {ars(quote.merchandise)}"
            )
            with st.expander("Detalle e IVA"):
                st.caption(
                    f"Sobrante {quantity_label(quote.surplus, offer.unit)} · "
                    f"{ars(quote.merchandise / quote.received)} por {offer.unit}"
                )
                tax_basis = st.selectbox(
                    "IVA confirmado",
                    list(TAX_OPTIONS),
                    format_func=TAX_OPTIONS.__getitem__,
                    key=f"iva_modo_{widget}",
                )
                rate = None
                if tax_basis != "pendiente":
                    entered = st.number_input(
                        "Alícuota confirmada (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=None,
                        step=1.0,
                        key=f"iva_tasa_{widget}",
                    )
                    if entered is not None:
                        rate = Decimal(str(entered)) / 100
                line = BudgetLine(quote, tax_basis, rate)
                st.caption(line.tax_label)
            st.button("Quitar", key=f"quitar_{widget}", on_click=remove_offer, args=(line_key,))
        lines.append(line)

    if len(lines) != len(cart):
        st.caption("Corregí las cantidades para calcular el presupuesto.")
        return

    shipping = {}
    with st.expander("Envío por proveedor"):
        sellers = {line.quote.offer.supplier.identifier: line.quote.offer.supplier for line in lines}
        for seller in sellers.values():
            label = (
                seller.name
                if seller.name != "Vendedor sin confirmar"
                else f"{seller.name} · {seller.identifier}"
            )
            amount = st.number_input(
                f"{label} (ARS)",
                min_value=0.0,
                value=None,
                step=100.0,
                placeholder="Sin confirmar",
                key=f"envio_{seller.identifier}",
            )
            if amount is not None:
                shipping[seller.identifier] = money(Decimal(str(amount)))

    orders = budget_orders(lines, shipping)
    complete = all(order.complete for order in orders)
    known = sum(order.known for order in orders)
    issued_at = datetime.now(timezone(timedelta(hours=-3)))
    with summary:
        st.metric(
            "Total estimado del pedido" if complete else "Importe conocido",
            ars(known),
        )
        merchandise = ars(sum(order.merchandise for order in orders))
        st.caption(f"Mercadería estimada · {merchandise}")
        if not complete:
            st.caption("Completá el IVA y el envío confirmados para estimar el total del pedido.")
        st.download_button(
            "Descargar presupuesto (PDF)",
            data=lambda: create_pdf(orders, issued_at),
            file_name=f"tacctico_presupuesto_{issued_at:%Y%m%d_%H%M}.pdf",
            mime="application/pdf",
            type="primary",
            width="stretch",
            on_click="ignore",
        )
    label = "Total estimado del pedido" if complete else "Importe conocido"
    pending = "" if complete else "Hay cargos por confirmar"
    # En la web pública se deja libre el distintivo del alojamiento.
    hosted = (urlsplit(st.context.url or "").hostname or "").endswith(".streamlit.app")
    host_class = " cloud-budget" if hosted else ""
    st.html(
        f'<aside class="mobile-budget{host_class}" aria-label="Resumen del presupuesto">'
        f"<div><span>{label}</span><strong>{escape(ars(known))}</strong><small>{pending}</small></div>"
        '<a href="#lista-de-compras">Ver presupuesto</a></aside>'
    )
    with st.expander("Desglose por proveedor"):
        st.dataframe(
            [
                {
                    "Proveedor": order.supplier,
                    "Mercadería": ars(order.merchandise),
                    "IVA a sumar conocido": ars(order.added_vat),
                    "Envío": ars(order.shipping),
                    "Importe conocido": ars(order.known),
                }
                for order in orders
            ],
            hide_index=True,
        )
