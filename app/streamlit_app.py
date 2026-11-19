from pathlib import Path

import pandas as pd
import streamlit as st

from purchase_data import market_csv
from purchase_view import show_calculator
from release_view import choose_release, show_dashboard
from catalog_view import ingredient_label, show_catalog


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "assets"
LOGO = ROOT / "app" / "static" / "logo-tacctico.png"
MARKET_CSV = market_csv(ROOT)
ORIGINAL_CSV = ROOT / "data_real" / "dataset_final.csv"
DOWNLOADED_CSV = Path.home() / "Downloads" / "dataset_final.csv"
MARKET_COLUMNS = [
    "id_publicacion", "titulo", "precio_publicado", "moneda", "url", "capturado_en", "fuente",
]
OPTIONAL_COLUMNS = ["insumo", "marca", "vendedor", "precio_100g", "revision_presentacion", "gramos_totales", "unidades"]


def show_market_offers():
    try:
        offers = pd.read_csv(
            MARKET_CSV, usecols=lambda column: column in MARKET_COLUMNS + OPTIONAL_COLUMNS,
            dtype={"id_publicacion": str},
        )
        if not set(MARKET_COLUMNS) <= set(offers.columns):
            raise ValueError("Faltan columnas obligatorias.")
        offers["precio_publicado"] = pd.to_numeric(offers["precio_publicado"], errors="raise")
        offers["capturado_en"] = pd.to_datetime(
            offers["capturado_en"], format="ISO8601", utc=True,
        ).dt.tz_localize(None)
        if {"precio_100g", "revision_presentacion"} <= set(offers.columns):
            offers["precio_100g"] = pd.to_numeric(offers["precio_100g"], errors="coerce").where(
                offers["revision_presentacion"].isna()
            )
        valid_prices = offers["precio_publicado"].between(0, float("inf"), inclusive="neither")
        valid_urls = offers["url"].astype("string").str.match(
            r"^https://articulo\.mercadolibre\.com\.ar/[^\s]+$", na=False,
        )
        if (
            offers.empty or offers[MARKET_COLUMNS].isna().any().any()
            or not (valid_prices & valid_urls & offers["moneda"].eq("ARS")).all()
        ):
            raise ValueError("El CSV no contiene publicaciones válidas en ARS.")
    except (OSError, ValueError) as error:
        st.error(f"No se pudo cargar el CSV validado ({MARKET_CSV.name}). {error}")
        return

    st.header("Catálogo de publicaciones", anchor=False)
    with st.container(key="filtros_catalogo"):
        search_col, ingredient_col = st.columns([2, 1])
        query = search_col.text_input("Buscar por título", key="titulo_real", placeholder="Por ejemplo, premezcla para pan").strip()
        ingredient_slot = ingredient_col.container()
        price_filters = st.expander("Filtrar por precio publicado")
    insumo = None
    if "insumo" in offers:
        insumo = ingredient_slot.selectbox(
            "Insumo", sorted(offers["insumo"].dropna().unique()),
            index=None, placeholder="Todos los insumos", format_func=ingredient_label,
            key="insumo_catalogo",
        )
    min_col, max_col = price_filters.columns(2)
    minimum = min_col.number_input(
        "Precio mínimo (ARS)", min_value=0.0, value=None, step=1.0,
        format="%.2f", placeholder="Sin mínimo", key="precio_minimo",
    )
    maximum = max_col.number_input(
        "Precio máximo (ARS)", min_value=0.0, value=None, step=1.0,
        format="%.2f", placeholder="Sin máximo", key="precio_maximo",
    )
    if minimum is not None and maximum is not None and minimum > maximum:
        st.error("El precio mínimo debe ser menor o igual al máximo.")
        return

    prices = offers["precio_publicado"]
    lower = float("-inf") if minimum is None else minimum
    upper = float("inf") if maximum is None else maximum
    matches = offers["titulo"].str.contains(query, case=False, regex=False)
    if insumo is not None:
        matches &= offers["insumo"].eq(insumo)
    filtered = offers[matches & prices.between(lower, upper)].sort_values(
        ["precio_publicado", "titulo"]
    )

    with st.container(key="catalogo_resumen"):
        count, origin = st.columns([1, 3], vertical_alignment="center")
        count.metric("Publicaciones visibles", len(filtered))
        origin.caption("Mercado Libre Argentina. El precio corresponde a la presentación publicada.")
    if filtered.empty:
        st.info("No hay publicaciones para estos filtros.")
        return

    show_catalog(filtered)


st.set_page_config(page_title="TACCtico", page_icon=str(LOGO), layout="wide", initial_sidebar_state="collapsed")
st.html(ASSETS / "tokens.css")
st.html(ASSETS / "theme.css")
# Solo código estático del repositorio; ningún dato del CSV se ejecuta como JavaScript.
st.html(f'<script>{(ASSETS / "navigation.js").read_text(encoding="utf-8")}</script>', unsafe_allow_javascript=True)
with st.container(key="app_navigation"):
    st.html("""
        <header class="tacctico-header">
            <img src="app/static/logo-tacctico.png?v=2" alt="TACCtico" width="64" height="64">
            <div><h1>Compras sin TACC</h1><p>Compará ofertas y armá el presupuesto de tu negocio.</p></div>
        </header>
    """)
    section = st.radio(
        "Sección", ["Catálogo", "Arma tu presupuesto", "Dashboard"], horizontal=True,
        key="seccion", label_visibility="collapsed",
    )
data_toolbar = st.container(key="datos_captura")
with data_toolbar:
    capture, update = st.columns([3, 1], vertical_alignment="center")
    refresh = update.button("Actualizar datos", key="actualizar_lote", help="Si hay un lote nuevo, empieza un presupuesto vacío.")
    release = choose_release(ROOT, refresh=refresh, controls=False)
    if release:
        date = (release["metrics"].get("captura_hasta") or "")[:10]
        date = "/".join(reversed(date.split("-"))) if date else "sin fecha"
        capture.caption(f"Precios de la captura del {date}", help=f"Fuente: Mercado Libre Argentina. Versión {release['lote'][:8]}.")
if release:
    MARKET_CSV = Path(release["folder"]) / "mercadolibre_validado.csv"
content_keys = {"Catálogo": "contenido_catalogo", "Arma tu presupuesto": "contenido_presupuesto", "Dashboard": "contenido_dashboard"}
with st.container(key=content_keys[section]):
    if section == "Dashboard":
        show_dashboard(release)
    elif section == "Arma tu presupuesto":
        original = next((path for path in (ORIGINAL_CSV, DOWNLOADED_CSV) if path.is_file()), None)
        show_calculator(MARKET_CSV, original)
    elif MARKET_CSV.is_file():
        show_market_offers()
    else:
        st.info("Guardá el CSV validado de Mercado Libre en data_real/mercadolibre_validado.csv.")
    st.html(f'<span class="tacctico-section-ready" data-section="{content_keys[section]}" aria-hidden="true"></span>')
