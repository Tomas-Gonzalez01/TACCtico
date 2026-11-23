"""Presentación del catálogo: números originales para ordenar y precios legibles."""

from decimal import Decimal
from html import escape
from math import ceil

import pandas as pd
import streamlit as st

from budget import ars, quantity_number
from ml_view import show_catalog_signals


INGREDIENTS = {
    "chips_chocolate": "Chips de chocolate",
    "levadura": "Levadura",
    "polvo_hornear": "Polvo de hornear",
    "premezcla_budin": "Premezcla para budín",
    "premezcla_pan": "Premezcla para pan",
    "premezcla_pizza": "Premezcla para pizza",
    "premezcla_universal": "Premezcla universal",
}


def readable(value):
    return "Sin dato" if pd.isna(value) or not str(value).strip() else str(value)


def ingredient_label(value):
    return INGREDIENTS.get(value, readable(value).replace("_", " ").capitalize())


def price_label(value):
    return "Sin dato" if pd.isna(value) else ars(Decimal(str(value)))


def presentation(row):
    if pd.notna(row.get("revision_presentacion")) and str(row["revision_presentacion"]).strip():
        return "Presentación por confirmar"
    total = row.get("gramos_totales")
    if pd.isna(total) or total is None or total <= 0:
        return "Contenido por confirmar"
    grams = Decimal(str(total))
    amount = f"{quantity_number(grams / 1000)} kg" if grams >= 1000 else f"{quantity_number(grams)} g"
    units = row.get("unidades")
    if units is not None and pd.notna(units) and units > 1:
        amount += f" en {quantity_number(Decimal(str(units)))} unidades"
    return amount


def display_frame(offers):
    frame = offers.drop(columns=["capturado_en", "revision_presentacion"], errors="ignore").copy()
    for name in ("marca", "vendedor"):
        if name in frame:
            frame[name] = frame[name].map(readable)
    if "insumo" in frame:
        frame["insumo"] = frame["insumo"].map(ingredient_label)
    frame["presentacion"] = offers.apply(presentation, axis=1)
    return frame


def show_catalog(offers):
    show_catalog_signals(offers)
    frame = display_frame(offers)
    formats = {name: price_label for name in ("precio_publicado", "precio_100g") if name in frame}
    with st.container(key="catalogo_tabla"):
        st.dataframe(
            frame.style.format(formats, na_rep="Sin dato"),
            hide_index=True,
            placeholder="Sin dato",
            column_order=[
                name
                for name in (
                    "titulo",
                    "precio_publicado",
                    "presentacion",
                    "precio_100g",
                    "vendedor",
                    "url",
                    "insumo",
                    "marca",
                )
                if name in frame
            ],
            column_config={
                "titulo": st.column_config.TextColumn("Producto", width="large"),
                "precio_publicado": "Precio publicado",
                "presentacion": "Presentación",
                "precio_100g": "Referencia por 100 g",
                "vendedor": "Vendedor",
                "insumo": "Insumo",
                "marca": "Marca",
                "url": st.column_config.LinkColumn("Publicación", display_text="Ver publicación"),
            },
            row_height=44,
        )
    with st.container(key="catalogo_tarjetas"):
        page_count = ceil(len(offers) / 12)
        page = st.selectbox(
            "Página de resultados",
            range(page_count),
            format_func=lambda n: f"{n + 1} de {page_count}",
            key="pagina_catalogo",
        )
        cards = []
        for _, row in offers.iloc[page * 12 : (page + 1) * 12].iterrows():
            reference = row.get("precio_100g")
            reference = (
                "Referencia de peso sin confirmar"
                if pd.isna(reference) or reference is None
                else f"{price_label(reference)} por 100 g"
            )
            title = escape(readable(row["titulo"]))
            cards.append(
                f'<article class="catalog-card"><h3>{title}</h3>'
                f'<p class="catalog-meta">{escape(ingredient_label(row.get("insumo")))}. {escape(readable(row.get("marca")))}</p>'
                f'<p class="catalog-price">{price_label(row["precio_publicado"])}</p>'
                f'<p>{escape(presentation(row))}</p><p class="catalog-meta">{escape(reference)}</p>'
                f"<p>Vendedor: {escape(readable(row.get('vendedor')))}</p>"
                f'<a href="{escape(row["url"], quote=True)}" target="_blank" rel="noopener noreferrer" '
                f'aria-label="Ver publicación de {title}">Ver publicación</a></article>'
            )
        st.html('<div class="catalog-cards">' + "".join(cards) + "</div>")
