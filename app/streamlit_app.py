from pathlib import Path

import pandas as pd
import streamlit as st

from purchase_data import market_csv
from purchase_view import show_calculator
from release_view import choose_release, show_dashboard


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "assets"
LOGO = ROOT / "app" / "static" / "logo-tacctico.png"
MARKET_CSV = market_csv(ROOT)
ORIGINAL_CSV = ROOT / "data_real" / "dataset_final.csv"
DOWNLOADED_CSV = Path.home() / "Downloads" / "dataset_final.csv"
MARKET_COLUMNS = [
    "id_publicacion", "titulo", "precio_publicado", "moneda", "url", "capturado_en", "fuente",
]
OPTIONAL_COLUMNS = ["insumo", "marca", "vendedor", "precio_100g", "revision_presentacion"]


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

    st.sidebar.subheader("Filtros del catálogo", anchor=False)
    query = st.sidebar.text_input("Buscar por título", key="titulo_real").strip()
    insumo = None
    if "insumo" in offers:
        insumo = st.sidebar.selectbox(
            "Insumo", sorted(offers["insumo"].dropna().unique()),
            index=None, placeholder="Todos los insumos", format_func=lambda value: value.replace("_", " "),
            key="insumo_catalogo",
        )
    minimum = st.sidebar.number_input(
        "Precio mínimo (ARS)", min_value=0.0, value=None, step=1.0,
        format="%.2f", placeholder="Sin mínimo", key="precio_minimo",
    )
    maximum = st.sidebar.number_input(
        "Precio máximo (ARS)", min_value=0.0, value=None, step=1.0,
        format="%.2f", placeholder="Sin máximo", key="precio_maximo",
    )
    if minimum is not None and maximum is not None and minimum > maximum:
        st.header("Catálogo de publicaciones", anchor=False)
        st.sidebar.error("El precio mínimo debe ser menor o igual al máximo.")
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
        title, count = st.columns([3, 1], vertical_alignment="center")
        title.header("Catálogo de publicaciones", anchor=False)
        title.caption("Mercado Libre Argentina")
        count.metric("Publicaciones visibles", len(filtered))
    if filtered.empty:
        st.info("No hay publicaciones para estos filtros.")
        return

    st.dataframe(
        filtered.drop(columns=["capturado_en", "revision_presentacion"], errors="ignore"),
        hide_index=True,
        column_order=[
            column for column in (
                "titulo", "precio_publicado", "insumo", "precio_100g", "marca", "vendedor", "url",
            ) if column in filtered.columns
        ],
        column_config={
            "insumo": "Insumo",
            "titulo": "Título",
            "marca": "Marca",
            "vendedor": "Vendedor",
            "precio_publicado": st.column_config.NumberColumn("Precio publicado (ARS)", format="%.2f"),
            "precio_100g": st.column_config.NumberColumn("Precio por 100 g (ARS)", format="%.2f"),
            "url": st.column_config.LinkColumn("Publicación", display_text="Abrir en Mercado Libre"),
        },
    )


st.set_page_config(page_title="TACCtico", page_icon=str(LOGO), layout="wide")
st.html(ASSETS / "theme.css")
st.html("""
    <header class="tacctico-header">
        <div>
            <h1>Compras sin TACC</h1>
            <p>Compará ofertas y armá el presupuesto de tu negocio.</p>
        </div>
        <img src="app/static/logo-tacctico.png?v=2" alt="TACCtico" width="144" height="144">
    </header>
""")
release = choose_release(ROOT)
if release:
    MARKET_CSV = Path(release["folder"]) / "mercadolibre_validado.csv"
section = st.radio(
    "Sección", ["Catálogo", "Arma tu presupuesto", "Dashboard"], horizontal=True,
    key="seccion", label_visibility="collapsed",
)
if section == "Dashboard":
    show_dashboard(release)
elif section == "Arma tu presupuesto":
    original = next((path for path in (ORIGINAL_CSV, DOWNLOADED_CSV) if path.is_file()), None)
    show_calculator(MARKET_CSV, original)
elif MARKET_CSV.is_file():
    show_market_offers()
else:
    st.info("Guardá el CSV validado de Mercado Libre en data_real/mercadolibre_validado.csv.")
