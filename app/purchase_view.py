from collections import Counter
from dataclasses import replace
from decimal import Decimal, InvalidOperation

import streamlit as st

from budget import ars, quantity_label, quantity_number
from budget_view import add_to_cart, choose_offer, quantity_field, show_budget
from catalog_view import ingredient_label
from purchase_data import load_publications
from purchase_engine import best_purchase, candidate_quotes, supplier_options
from recipe_plan import DEFAULT_MAX_BATCHES, RECIPES, plan_for_budget, typical_batches


UNITS = {"kg": "kg", "unidad": "unidades"}
LINK = st.column_config.LinkColumn("Publicación", display_text="Abrir en Mercado Libre")


def quantity_input(unit, key):
    if unit == "unidad":
        return quantity_field("Unidades requeridas", f"{key}_unidad", default=Decimal(1), whole_units=True)
    amount_column, measure_column = st.columns([2, 1])
    with measure_column:
        measure = st.selectbox("Medida", ["kg", "g"], key=f"{key}_medida")
    with amount_column:
        amount = quantity_field(
            f"Cantidad requerida ({measure})",
            f"{key}_{measure}",
            default=Decimal(1),
        )
    return amount / 1000 if measure == "g" else amount


def options_for(publications, needed, unit, **limits):
    quotes = []
    unavailable = []
    for publication in publications:
        offer = publication.offer
        if unit == "unidad":
            offer = replace(offer, unit=unit, pack=Decimal(publication.units) if publication.units else None)
        try:
            quotes.extend(candidate_quotes(offer, needed, unit, published=True, **limits))
        except ValueError:
            unavailable.append(
                {
                    "Título": offer.product,
                    "Proveedor": offer.supplier.name,
                    "Motivo": publication.review
                    or f"Contenido en {UNITS[unit]} sin confirmar para esta presentación",
                    "Publicación": offer.url,
                }
            )
    return quotes, unavailable


def weight_label(kg):
    if kg is None:
        return "Sin dato"
    return f"{quantity_number(kg * 1000)} g" if kg < 1 else quantity_label(kg, "kg")


def sort_quotes(quotes):
    return sorted(quotes, key=lambda quote: (quote.offer.outlier_price, quote.merchandise, quote.surplus))


def seller_labels(publications):
    sellers = {item.offer.supplier.identifier: item.offer.supplier.name for item in publications}
    counts = Counter(sellers.values())
    return {
        seller: f"{name} · {seller.removeprefix('publicación:')}" if counts[name] > 1 else name
        for seller, name in sellers.items()
    }


def show_quotes(quotes, unit, product_key=None):
    if not quotes:
        return
    rows = []
    for quote in quotes:
        offer = quote.offer
        row = {
            "Proveedor": quote.offer.supplier.name,
            "Título": quote.offer.product,
            "Presentaciones": quote.boxes,
            "Recibís": quantity_label(quote.received, unit),
            "Sobrante": quantity_label(quote.surplus, unit),
            "Mercadería estimada": ars(quote.merchandise),
            f"Precio publicado por {'kg' if unit == 'kg' else 'unidad'}": ars(
                quote.merchandise / quote.received
            ),
            "Publicación": quote.offer.url,
            "Envío en la captura": quote.offer.shipping_note or "Sin dato",
            "Promoción publicada": quote.offer.promotion or "Sin dato",
            "Revisión de precio": "Precio atípico" if quote.offer.outlier_price else "",
        }
        if unit == "kg":
            units = offer.units_per_pack
            row.update(
                {
                    "Peso por unidad": weight_label(offer.pack / units if units else None),
                    "Unidades por pack": quantity_number(units) if units else "Sin dato",
                    "Peso por pack": weight_label(offer.pack),
                }
            )
        rows.append(row)

    if product_key is not None:
        choose_offer(quotes, key="seleccionar_oferta")
    with st.expander("Ver detalle de las ofertas", expanded=product_key is None):
        st.dataframe(rows, hide_index=True, column_config={"Publicación": LINK})


def show_recommendation(quote, unit, label):
    with st.container(border=True, key="oferta_recomendada"):
        st.metric(label, ars(quote.merchandise))
        presentation = "presentación" if quote.boxes == 1 else "presentaciones"
        st.write(quote.offer.supplier.name)
        st.caption(
            f"{quote.boxes} {presentation} · Recibís {quantity_label(quote.received, unit)}"
            f" · Sobrante {quantity_label(quote.surplus, unit)}"
        )


def show_supplier_purchase(publications, needed, unit, product_key, *, compare_sizes=False):
    sellers = seller_labels(publications)
    supplier = st.selectbox("Proveedor", list(sellers), format_func=sellers.__getitem__)
    selected = [item for item in publications if item.offer.supplier.identifier == supplier]
    budget = st.number_input("Presupuesto máximo de mercadería (ARS)", min_value=0.0, value=None, step=100.0)
    try:
        max_quantity = quantity_field(
            f"Cantidad máxima ({UNITS[unit]})",
            f"maximo_{unit}",
            whole_units=unit == "unidad",
        )
    except ValueError as error:
        st.error(str(error))
        return []
    quotes, unavailable = options_for(selected, needed, unit)
    eligible = [quote for quote in quotes if not quote.offer.outlier_price]
    minimum, best = supplier_options(eligible, bounded=False, published=True)
    bounded = budget is not None or max_quantity is not None
    visible_quotes = quotes
    if bounded:
        visible_quotes, _ = options_for(
            selected,
            needed,
            unit,
            budget=Decimal(str(budget)) if budget is not None else None,
            max_quantity=max_quantity,
        )
        _, best = supplier_options(
            [quote for quote in visible_quotes if not quote.offer.outlier_price],
            bounded=True,
            published=True,
        )
    if minimum is None:
        if quotes:
            st.info("Las ofertas de este vendedor tienen precios atípicos. Revisalas antes de elegir.")
            show_quotes(sort_quotes(visible_quotes), unit, product_key)
        else:
            st.info("Faltan datos de presentación para calcular esta compra.")
    elif best is None:
        st.info("Ninguna presentación comparable cubre tu necesidad dentro del límite indicado.")
        st.caption("Compra mínima estimada fuera del límite")
        show_quotes([minimum], unit)
        show_quotes(sort_quotes(visible_quotes), unit, product_key)
    else:
        show_recommendation(best, unit, "Mercadería estimada · Compra sugerida")
        if best != minimum:
            delta = best.merchandise - minimum.merchandise
            st.caption(
                f"Frente a la compra mínima: {quantity_label(best.received - minimum.received, unit)} "
                f"adicionales y {ars(abs(delta))} {'más' if delta >= 0 else 'menos'} en mercadería."
            )
        quotes = [minimum, best] if best != minimum and not bounded else [best]
        if bounded and best != minimum:
            st.caption(f"Compra mínima de referencia · {ars(minimum.merchandise)}")
        show_quotes(
            sort_quotes(visible_quotes) if compare_sizes else quotes,
            unit,
            product_key,
        )
    return unavailable


def show_calculator(snapshot, original):
    st.header("Arma tu presupuesto", anchor=False)
    if not snapshot.is_file():
        st.info("Guardá el CSV validado de Mercado Libre en data_real/mercadolibre_validado.csv.")
        return
    try:
        products = load_publications(snapshot, original)
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation) as error:
        st.error(f"No se pudieron cargar los CSV de Mercado Libre. {error}")
        return
    if not products:
        st.info("El CSV validado no contiene publicaciones.")
        return

    st.caption(
        "Estimaciones con precios capturados en Mercado Libre. "
        "Confirmá disponibilidad, IVA, mínimo, promociones y envío al cerrar el pedido."
    )
    with st.container(key="calculadora"):
        comparison, budget = st.columns([3, 2], gap="medium")
        with comparison:
            with st.container(border=True, key="comparar_ofertas"):
                st.subheader("Comparar ofertas")
                show_comparison(products)
        with budget:
            with st.container(border=True, key="presupuesto"):
                show_budget()


def select_weight_offers(products, insumos, mode):
    insumo = st.selectbox("Insumo", insumos, format_func=lambda value: value.replace("_", " ").capitalize())
    quantity_slot = st.container()
    publications = [item for group in products.values() for _, item in group if item.insumo == insumo]
    with st.expander("Acotar ofertas"):
        brand_options = sorted(
            {item.brand or "Marca sin confirmar" for item in publications}, key=str.casefold
        )
        brands = st.multiselect("Marca", brand_options)
        if brands:
            publications = [item for item in publications if (item.brand or "Marca sin confirmar") in brands]

        if mode == "Por cantidad":
            sellers = seller_labels(publications)
            sellers_selected = st.multiselect(
                "Proveedor",
                sorted(sellers, key=lambda seller: (sellers[seller].casefold(), seller)),
                format_func=sellers.__getitem__,
            )
            if sellers_selected:
                publications = [
                    item for item in publications if item.offer.supplier.identifier in sellers_selected
                ]

        labels = {
            item.offer.listing: f"{item.offer.product} · {item.offer.supplier.name} · {item.offer.listing}"
            for item in publications
        }
        chosen = st.multiselect(
            "Publicaciones para comparar",
            sorted(labels, key=lambda listing: labels[listing].casefold()),
            format_func=labels.__getitem__,
            placeholder="Todas las filtradas",
        )
        if chosen:
            publications = [item for item in publications if item.offer.listing in chosen]
    return ("insumo_por_peso", insumo), publications, quantity_slot


def select_presentation(products, insumos):
    if insumos:
        insumo = st.selectbox(
            "Insumo",
            insumos,
            index=None,
            placeholder="Todos los insumos",
            format_func=lambda value: value.replace("_", " "),
        )
        if insumo:
            products = {key: group for key, group in products.items() if group[0][1].insumo == insumo}
    ordered = sorted(
        products,
        key=lambda key: (
            -sum(bool(item.offer.pack) for _, item in products[key]),
            products[key][0][0].casefold(),
        ),
    )
    names_by_key = {key: group[0][0] for key, group in products.items()}
    names = Counter(names_by_key.values())
    labels = {
        key: name if names[name] == 1 else f"{name} · {products[key][0][1].offer.listing}"
        for key, name in names_by_key.items()
    }
    key = st.selectbox("Insumo y presentación", ordered, format_func=labels.__getitem__)
    return key, [item for _, item in products[key]]


def recipe_settings(recipe_name):
    """Gramos por lote y tope de lotes; los valores iniciales son provisorios."""
    with st.expander("Ajustar receta"):
        items = tuple(
            replace(
                item,
                grams=Decimal(
                    str(
                        st.number_input(
                            f"{ingredient_label(item.insumo)} por lote (g)",
                            min_value=1.0,
                            value=float(item.grams),
                            step=1.0,
                            format="%g",
                            key=f"receta_{list(RECIPES).index(recipe_name)}_{item.insumo}",
                        )
                    )
                ),
            )
            for item in RECIPES[recipe_name]
        )
        max_batches = st.number_input(
            "Máximo de lotes a planificar",
            min_value=1,
            value=DEFAULT_MAX_BATCHES,
            step=1,
            key="receta_tope_lotes",
        )
        st.caption(
            "Un lote usa las cantidades indicadas arriba. Son ejemplos editables: cargá los de tu receta. "
            "El límite de lotes es una decisión de planificación; no calcula vencimientos."
        )
    return items, int(max_batches)


def show_recipe_plan(products):
    publications = [item for group in products.values() for _, item in group]
    recipe_name = st.selectbox("Receta", list(RECIPES))
    budget = st.number_input(
        "Presupuesto para tu receta (ARS)", min_value=0.0, value=None, step=1000.0, key="presupuesto_receta"
    )
    items, max_batches = recipe_settings(recipe_name)
    if budget is None:
        st.info("Ingresá cuánto querés gastar en mercadería para ver cuántos lotes alcanzan.")
        return
    amount = Decimal(str(budget))
    st.caption(
        "El monto cubre solo la mercadería de los insumos listados: una publicación por insumo "
        "y envases de hasta 5 kg. Otros ingredientes quedan fuera; IVA y envío requieren confirmación."
    )
    plan = plan_for_budget(publications, items, amount, max_batches=max_batches)
    if plan is None:
        st.info("Faltan ofertas comparables de algún insumo de la receta para calcular la compra.")
        return
    if plan.batches == 0:
        st.info(
            f"Con {ars(amount)} no alcanza para un lote. La compra mínima de un lote cuesta {ars(plan.spend)}."
        )
        show_quotes(plan.quotes, "kg")
        return

    with st.container(border=True, key="plan_receta"):
        st.metric("Lotes que alcanzan", plan.batches)
        st.caption(
            f"Mercadería estimada {ars(plan.spend)} · {ars(plan.cost_per_batch)} por lote"
            f" · Te sobran {ars(plan.remaining)}"
        )
    typical = typical_batches(publications, items, amount, max_batches=max_batches)
    if typical is not None:
        st.caption(
            f"Referencia: comprando la oferta mediana de cada insumo, el mismo presupuesto alcanza "
            f"para {typical} {'lote' if typical == 1 else 'lotes'}."
        )
    if plan.batches == max_batches:
        st.caption("El plan llegó al máximo de lotes elegido; podés cambiarlo en «Ajustar receta».")
    if st.button("Agregar esta compra a mi lista", key="agregar_plan_receta"):
        for quote in plan.quotes:
            add_to_cart(quote)
    st.caption(
        "El resto de tu lista se conserva. Si una publicación ya está agregada, se actualiza su cantidad."
    )
    show_quotes(plan.quotes, "kg")


def show_comparison(products):
    mode_column, unit_column = st.columns([3, 2])
    mode = mode_column.radio(
        "¿Cómo querés calcular?", ["Por cantidad", "Por proveedor", "Por presupuesto"], horizontal=True
    )
    if mode == "Por presupuesto":
        show_recipe_plan(products)
        return
    unit = unit_column.radio(
        "Comparar por",
        ["kg", "unidad"],
        format_func={"kg": "Peso (kg o g)", "unidad": "Unidades"}.__getitem__,
        horizontal=True,
    )
    insumos = sorted({item.insumo for group in products.values() for _, item in group if item.insumo})
    compare_sizes = unit == "kg" and bool(insumos)
    if compare_sizes:
        key, publications, quantity_slot = select_weight_offers(products, insumos, mode)
    else:
        key, publications = select_presentation(products, insumos)
        quantity_slot = st.container()
    if not publications:
        st.info("No hay ofertas con los filtros elegidos.")
        return
    try:
        with quantity_slot:
            needed = quantity_input(unit, "cantidad_requerida")
    except ValueError as error:
        st.error(str(error))
        return

    if mode == "Por cantidad":
        quotes, unavailable = options_for(publications, needed, unit)
        best = best_purchase([quote for quote in quotes if not quote.offer.outlier_price], published=True)
        if best is not None:
            label = (
                "Menor importe sin alerta de precio"
                if any(quote.offer.outlier_price for quote in quotes)
                else "Menor importe publicado"
            )
            show_recommendation(best, unit, label)
        elif quotes:
            st.info("Las ofertas comparables tienen precios atípicos. Revisalas antes de elegir.")
        else:
            st.info("No se pudo confirmar el contenido de ninguna presentación para esta medida.")
        show_quotes(sort_quotes(quotes), unit, key)
    else:
        unavailable = show_supplier_purchase(publications, needed, unit, key, compare_sizes=compare_sizes)

    if unavailable:
        with st.expander(f"No comparables ({len(unavailable)})"):
            st.dataframe(unavailable, hide_index=True, column_config={"Publicación": LINK})
