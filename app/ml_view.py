"""Señales precalculadas del mismo lote. La web no entrena ni carga modelos externos."""

from decimal import Decimal

import streamlit as st
from budget import ars


def prediction(listing):
    release = st.session_state.get("lote_datos") or {}
    return release.get("metrics", {}).get("ml", {}).get("predicciones", {}).get(str(listing), {})


def price_notice(listing):
    return " · Precio para revisar" if prediction(listing).get("revisar") else ""


def show_price_detail(listing):
    result = prediction(listing)
    if result.get("estado") != "evaluado":
        return
    if result.get("revisar"):
        st.warning("Precio para revisar: puede ser una oferta legítima. Comprobá la publicación.")
    reference = ars(Decimal(str(result["precio_referencia_kg"])))
    st.caption(f"Referencia estimada con la captura: {reference} por kg. No reemplaza el precio publicado.")


def show_catalog_signals(offers):
    flagged = offers[offers["id_publicacion"].map(lambda value: prediction(value).get("revisar", False))]
    if flagged.empty:
        return
    with st.expander(f"{len(flagged)} ofertas con precio para revisar"):
        st.caption("El modelo señala precios inusuales; una señal no prueba un error ni descarta la oferta.")
        for _, row in flagged.iterrows():
            st.markdown(f"**{row['titulo']}**")
            show_price_detail(row["id_publicacion"])
            st.link_button("Revisar publicación", row["url"])
