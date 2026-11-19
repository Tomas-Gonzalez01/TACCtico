"""Actualiza el dashboard y las métricas de Kiara con el mismo lote del catálogo."""
import hashlib
import html
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

CATEGORIES = {"levadura": "Levadura", "polvo_hornear": "Polvo de hornear",
    "chips_chocolate": "Chips de chocolate", "premezcla_pan": "Premezcla pan",
    "premezcla_pizza": "Premezcla pizza", "premezcla_budin": "Premezcla budín",
    "premezcla_universal": "Premezcla universal"}
RECETAS = {"Pan": {"premezcla_pan": 500, "levadura": 10},
           "Pizza": {"premezcla_pizza": 250}, "Budin": {"premezcla_budin": 250}}
TEMPLATE = Path(__file__).with_name("templates") / "dashboard_kiara.html"


def serializable(value):
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serializable(v) for v in value]
    if value is None or (isinstance(value, (float, np.floating)) and not np.isfinite(value)):
        return None
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def dumps(value):
    return json.dumps(serializable(value), ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def analizar(util, summary):
    # Same cohort as the supplied notebook and final dashboard: useful, no outliers.
    base = util.loc[~util["outlier_precio"]].copy()
    base["precio_kg"] = base["precio_100g"] * 10
    aggregates = []
    for insumo, group in base.groupby("insumo", sort=True):
        price = group["precio_kg"]
        accessible = group.loc[group["gramos_totales"] <= 5000]
        # The final HTML limits both accessible and trusted offers to 5 kg.
        trusted = accessible.loc[accessible["nivel_vendedor"].isin(["platinum", "gold"])]
        median = price.median()
        best = accessible["precio_kg"].min()
        aggregates.append({"insumo": insumo, "categoria": CATEGORIES.get(insumo, insumo),
            "publicaciones": len(group), "vendedores": group["vendedor"].nunique(),
            "min_kg": price.min(), "p25_kg": price.quantile(.25), "mediana_kg": median,
            "media_kg": price.mean(), "p75_kg": price.quantile(.75), "max_kg": price.max(),
            "cv": price.std() / price.mean(), "mejor_accesible_kg": best,
            "mejor_confiable_kg": trusted["precio_kg"].min(),
            "brecha_mejor_vs_mediana": 1 - best / median})
    by_ingredient = {row["insumo"]: row for row in aggregates}
    recipes = {}
    for name, ingredients in RECETAS.items():
        if not all(i in by_ingredient and np.isfinite(by_ingredient[i]["mejor_accesible_kg"]) for i in ingredients):
            continue
        median = sum(g / 1000 * by_ingredient[i]["mediana_kg"] for i, g in ingredients.items())
        best = sum(g / 1000 * by_ingredient[i]["mejor_accesible_kg"] for i, g in ingredients.items())
        recipes[name] = {"med": median, "best": best, "ah": median - best}
    records = []
    for _, row in base.iterrows():
        def safe(value, default=""):
            return html.escape(default if pd.isna(value) else str(value), quote=True)
        records.append({"c": CATEGORIES.get(row["insumo"], row["insumo"]),
            "t": safe(row["titulo"]), "v": safe(row["vendedor"], "(sin dato)"),
            "n": safe(row["nivel_vendedor"], "s/d"), "p": float(row["precio"]),
            "g": float(row["gramos_totales"]), "pk": float(row["precio_kg"]),
            "f": "Pack" if row["es_pack"] else "Unidad",
            "eg": int(str(row.get("envioGratis", "")).lower() in {"true", "1"}),
            "gl": safe(row.get("libre_gluten"), "No declara"), "u": safe(row["link"])})
    captures = sorted(base["Tiempo"].dropna().astype(str).unique())
    dates = sorted({date[:10] for date in captures})
    date_label = " — ".join((dates[0], dates[-1])) if dates else "Sin fecha"
    if len(dates) == 1:
        date_label = dates[0]
    metrics = {"schema_version": 1, "lote": summary["lote"],
        "version_reglas": summary["version_reglas"], "moneda": "ARS",
        "captura_desde": captures[0] if captures else None,
        "captura_hasta": captures[-1] if captures else None,
        "catalogo": summary["publicaciones_tacctico"], "base_util": len(util),
        "base_sin_atipicos": len(base), "atipicos_excluidos": len(util) - len(base),
        "vendedores": int(base["vendedor"].nunique()), "por_insumo": aggregates,
        "lote_recetas": recipes,
        "supuestos": {"tope_accesible_gramos": 5000, "gramos_por_receta": RECETAS,
            "lotes_mensuales": {"bajo": 40, "medio": 120, "alto": 300},
            "minutos_manuales_por_insumo": 15, "minutos_herramienta_por_insumo": 2,
            "insumos_por_compra": 4, "compras_por_mes": 4,
            "referencias_equipo_ars_hora": [1994, 6529]},
        "metodo": "Notebook ETL/EDA de Kiara y dashboard final entregado el 19/11/2026. Base útil sin outliers; mediana frente a mejor publicación de hasta 5 kg.",
        "limitaciones": ["Precios de la captura, sin actualización comercial en tiempo real.",
            "Las brechas son estimaciones estadísticas y no un ahorro observado.",
            "Las recetas, frecuencia, tiempos y valor de la hora son supuestos editables.",
            "Arma tu presupuesto verifica presentaciones y cargos para una compra concreta.",
            "No se estima una tendencia temporal con una sola captura."]}
    meta = serializable({"n": len(base), "lote": recipes, "id_lote": summary["lote"]})
    # Protect the script boundary; text fields are escaped before HTML rendering.
    js_data = json.dumps(records, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    js_meta = json.dumps(meta, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    document = TEMPLATE.read_text(encoding="utf-8").replace("__TACCTICO_DATOS__", js_data).replace(
        "__TACCTICO_META__", js_meta).replace("__TACCTICO_FECHA__", html.escape(date_label))
    return {"metricas.json": dumps(metrics), "dashboard.html": document}


def paquete_publicable(result):
    # Raw input, rejected rows, account IDs and filesystem paths stay local.
    names = ("mercadolibre_validado.csv", "metricas.json", "dashboard.html", "calidad.json")
    public = {name: result["archivos"][name].encode("utf-8") for name in names}
    manifest = {"schema_version": 1, "lote": result["resumen"]["lote"],
        "archivos": {name: {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
                     for name, content in public.items()}}
    public["manifest.json"] = dumps(manifest).encode("utf-8")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(public.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return stream.getvalue()
