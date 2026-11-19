"""Mantiene catálogo, presupuesto y análisis en una única versión por sesión."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from data_release import load_local, load_remote, remote_id


def choose_release(root, *, refresh=False, controls=True):
    messages = st.sidebar if controls else st
    current = st.session_state.get("lote_datos")
    refresh = st.sidebar.button(
        "Actualizar datos", help="Si hay un lote nuevo, se empieza un presupuesto vacío para usar sus precios.",
        key="actualizar_lote",
    ) if controls else refresh
    if current is None or refresh:
        try:
            pointer = remote_id(root)
            candidate = load_remote(pointer) if pointer else load_local(root)
            if candidate and (current is None or candidate["lote"] != current["lote"]):
                if current is not None:
                    # Clear widget selections as well as quotes from the previous immutable lot.
                    for key in list(st.session_state):
                        if key not in {"seccion", "actualizar_lote"}:
                            del st.session_state[key]
                st.session_state["lote_datos"] = candidate
                current = candidate
                if refresh:
                    messages.success("Datos actualizados. Podés armar un nuevo presupuesto.")
            elif refresh:
                messages.info("Ya estás usando la última versión disponible.")
        except (OSError, ValueError, KeyError, TypeError) as error:
            if current is None:
                try:
                    current = load_local(root)
                    if current:
                        st.session_state["lote_datos"] = current
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            messages.warning("No se pudo actualizar. Se conserva la última versión disponible.")
    if current and controls:
        metrics = current["metrics"]
        date = (metrics.get("captura_hasta") or "Sin fecha")[:10]
        st.sidebar.caption(f"Precios capturados: {date} · Versión {current['lote'][:8]}")
    return current


def show_dashboard(release):
    st.header("Análisis de abastecimiento", anchor=False)
    if release is None:
        st.info("El análisis estará disponible cuando se complete un lote con el flujo de n8n.")
        return
    metrics = release["metrics"]
    st.caption(
        f"{metrics['catalogo']} publicaciones en el catálogo · "
        f"{metrics['base_sin_atipicos']} en el análisis de precios. "
        "El análisis usa la selección de Kiara sin precios atípicos; las brechas son estimaciones."
    )
    folder = Path(release["folder"])
    with st.expander("Cómo se calculan los resultados"):
        st.write(metrics["metodo"])
        for limitation in metrics["limitaciones"]:
            st.write("• " + limitation)
        st.download_button("Descargar métricas", (folder / "metricas.json").read_bytes(),
                           file_name="metricas_tacctico.json", mime="application/json")
        st.download_button("Descargar dashboard", (folder / "dashboard.html").read_bytes(),
                           file_name="dashboard_tacctico.html", mime="text/html")
    components.html((folder / "dashboard.html").read_text(encoding="utf-8"), height=1550, scrolling=True)
